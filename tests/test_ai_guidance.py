import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import torch

from backend import bridge
from ai.agents import ModelAgent
from ai.browser_bridge import decision
from ai.checkpoints import load_checkpoint, save_checkpoint, weight_fingerprint
from ai.export_browser import export_models
from ai.modules import ModuleEnv
from ai.nn_model import ActorCritic, GuidedResidualActorCritic, ResidualActorCritic
from ai.train import collect_rollout, ppo_update
from ai.train_fuel import successful_replay


class GuidanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_finite_prior_preserves_initial_choice_but_departures_can_learn(self):
        source = ActorCritic(489, 217, hidden_size=16)
        with torch.no_grad(): source.actor.bias[1] = 1000.
        model = GuidedResidualActorCritic(source, 489, 217, hidden_size=24)
        observations = torch.randn(3, 489)
        mask = torch.zeros(3, 217, dtype=torch.bool)
        mask[:, :2] = True
        reference = torch.zeros_like(mask)
        reference[:, 0] = True
        logits, value = model.policy_output(observations, reference)
        torch.testing.assert_close(value, source(observations)[1])
        torch.testing.assert_close(logits[:, 0] - logits[:, 1], torch.full((3,), 4.))
        actions, _, _ = model.act(observations, mask, deterministic=True, reference_mask=reference)
        self.assertEqual(actions.tolist(), [0, 0, 0])
        dist, _ = model.distribution(observations, mask, reference_mask=reference)
        self.assertTrue(bool((dist.probs[:, 1] > 0).all()))
        (-dist.log_prob(torch.ones(3, dtype=torch.long)).mean()).backward()
        self.assertGreater(float(model.residual.actor.bias.grad[1].abs()), 0.)
        self.assertTrue(all(p.grad is None for p in source.parameters()))
        with torch.no_grad(): model.residual.actor.bias[1] = 5.
        actions, _, _ = model.act(observations, mask, deterministic=True, reference_mask=reference)
        self.assertEqual(actions.tolist(), [1, 1, 1])
        with self.assertRaises(ValueError): model.act(observations, mask)
        with self.assertRaises(ValueError): ResidualActorCritic(model, 489, 217)
        bad = reference.clone()
        bad[:, 2] = True
        with self.assertRaises(ValueError): model.act(observations, mask, reference_mask=bad)

    def test_initial_whole_games_match_the_frozen_player(self):
        source = ActorCritic(489, 217, hidden_size=16)
        model = GuidedResidualActorCritic(source, 489, 217, hidden_size=24)
        old_agent, new_agent = ModelAgent(source), ModelAgent(model)
        for route in ('LOG_OSL_GREEN', 'LOG_HND_GREEN', 'LOG_LHR_GREEN'):
            old, new = ModuleEnv(route, assistance_version=7), ModuleEnv(route, assistance_version=9)
            old.reset(seed=41)
            _, info = new.reset(seed=41)
            while not old.done:
                self.assertEqual(old.observation(), new.observation())
                self.assertEqual(old.action_mask(), info['reference_action_mask'])
                a = old_agent.select(old.view(), old.action_mask())
                b = new_agent.select(new.view(), info['action_mask'], reference_mask=info['reference_action_mask'])
                self.assertEqual(a, b)
                old.step(a)
                _, _, _, _, info = new.step(b)
            self.assertTrue(new.done)
            self.assertEqual(old.episode_record(41, 'both', 0), new.episode_record(41, 'both', 0))

    def test_public_reference_is_identical_in_browser_and_hides_partner_faces(self):
        env = ModuleEnv('LOG_OSL_GREEN', assistance_version=9)
        _, info = env.reset(seed=46)
        previous = bridge._spiel
        try:
            bridge._spiel = env.game
            before = decision(assistance_version=9, schema_version=3)
            self.assertEqual(before['reference_action_mask'], info['reference_action_mask'])
            self.assertEqual(before['action_mask'], info['action_mask'])
            self.assertNotIn('own_dice', before['public_state'])
            for die in env.game._wuerfel_liste(env.other_role(env.current_role)):
                if die.ist_verfuegbar(): die.augenzahl = 7 - die.augenzahl
            self.assertEqual(before, decision(assistance_version=9, schema_version=3))
        finally:
            bridge._spiel = previous

    def test_real_ppo_and_imitation_keep_reference_masks_and_frozen_weights(self):
        source = ActorCritic(489, 217, hidden_size=16)
        model = GuidedResidualActorCritic(source, 489, 217, hidden_size=24)
        frozen = weight_fingerprint(source)
        env = ModuleEnv('LOG_OSL_GREEN', assistance_version=9)
        batch, records = collect_rollout(model, env, 64, seed='guidance-unit', episodes_done=0, gamma=.995, gae_lambda=.95)
        self.assertEqual(batch['reference_masks'].dtype, torch.bool)
        self.assertFalse(bool((batch['reference_masks'] & ~batch['masks']).any()))
        demos = {k: batch[k][:8] for k in ('observations', 'masks', 'actions', 'reference_masks')}
        before = model.residual.actor.weight.detach().clone()
        stats = ppo_update(model, torch.optim.Adam(model.parameters(), lr=.001), batch, epochs=1, minibatch_size=64,
                           clip=.2, value_coef=.5, entropy_coef=.01, demonstrations=demos, demo_coef=.03)
        self.assertTrue(torch.isfinite(torch.tensor(stats['policy_loss'])))
        self.assertFalse(torch.equal(before, model.residual.actor.weight))
        self.assertEqual(frozen, weight_fingerprint(source))
        # A synthetic two-episode fixture checks the replay contract separately
        # from the real PPO games; it is not counted as a training win.
        replay = successful_replay({k: v[:3] for k, v in batch.items()},
                                   [{'status':'gewonnen','steps':2}, {'status':'verloren','steps':1}])
        self.assertTrue(torch.equal(replay['reference_masks'], batch['reference_masks'][:2]))

    @unittest.skipUnless(shutil.which('node'), 'node required')
    def test_guided_checkpoint_and_js_policy_match_native(self):
        source = ResidualActorCritic(ActorCritic(hidden_size=16), 489, 217, hidden_size=24)
        model = GuidedResidualActorCritic(source, 489, 217, hidden_size=24)
        torch.nn.init.normal_(model.residual.actor.weight, std=.05)
        observations = torch.randn(6, 489)
        masks = torch.rand(6, 217) > .5
        masks[:, 0] = True
        refs = (torch.rand(6, 217) > .7) & masks
        refs[:, 0] = True
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'runs/guided/best.pt'
            save_checkpoint(path, model, train_config={'assistance_version':9})
            loaded, _ = load_checkpoint(path)
            torch.testing.assert_close(model.policy_output(observations, refs)[0], loaded.policy_output(observations, refs)[0])
            catalog = export_models(root / 'runs', root / 'web')
            entry = catalog['models'][0]
            fixture = {'model':json.loads((root / 'web' / entry['url']).read_text()), 'catalog':{'schema':entry['schema']},
                       'observations':observations.tolist(), 'masks':masks.tolist(), 'references':refs.tolist()}
            script = """const fs=require('node:fs');global.window={};eval(fs.readFileSync(process.argv[1],'utf8'));
const f=JSON.parse(fs.readFileSync(0,'utf8')),p=window.CockpitPolicy.create(f.model,f.catalog);
process.stdout.write(JSON.stringify(f.observations.map((o,i)=>({logits:p.logits(o,f.references[i]),
choice:p.select({observation:o,action_mask:f.masks[i],reference_action_mask:f.references[i]})}))));"""
            result = subprocess.run(['node', '-e', script, str(Path(__file__).resolve().parents[1] / 'frontend/web/js/ai-policy.js')],
                                    input=json.dumps(fixture), text=True, capture_output=True, check=True)
            rows = json.loads(result.stdout)
            torch.testing.assert_close(model.policy_output(observations, refs)[0], torch.tensor([r['logits'] for r in rows]), atol=2e-6, rtol=1e-6)
            expected = model.act(observations, masks, deterministic=True, reference_mask=refs)[0].tolist()
            self.assertEqual(expected, [r['choice'] for r in rows])


if __name__ == '__main__':
    unittest.main()
