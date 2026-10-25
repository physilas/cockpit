from copy import deepcopy
import json
from pathlib import Path
import unittest

from ai.modules import ModuleEnv,MODULE_ACTIONS,MODULE_FEATURES,MODULES
from ai.pretrain_rules import public_exercises,public_effect,EFFECTS


class RuleCurriculumTests(unittest.TestCase):
    def test_exercises_use_legal_actions_and_cover_public_module_effects(self):
        cases=json.loads((Path(__file__).resolve().parents[1]/'ai/experiments/modules-50pct-2026-10-25/matrix.json').read_text())['cases']
        chosen=[]
        for module in MODULES:
            case=next(c for c in cases if module in c['modules'])
            if case not in chosen:chosen.append(case)
        obs,masks,actions,effects=public_exercises((chosen,24,'rule-unit:251025',3,1))
        self.assertTrue(obs)
        for x,mask,a,delta in zip(obs,masks,actions,effects):
            self.assertEqual(len(x),len(MODULE_FEATURES))
            self.assertEqual(len(mask),len(MODULE_ACTIONS))
            self.assertTrue(mask[a])
            self.assertEqual(len(delta),len(EFFECTS))
        for name in ('fuel','wind_sin','ice','intern'):
            self.assertTrue(any(abs(row[EFFECTS.index(name)])>1e-6 for row in effects),name)

    def test_public_consequences_ignore_unplaced_partner_faces(self):
        env=ModuleEnv('LOG_OSL_GREEN',clock=lambda:0);env.reset(seed=46)
        other=deepcopy(env)
        for die in other.game._wuerfel_liste(other.other_role(other.current_role)):
            if die.ist_verfuegbar():die.augenzahl=7-die.augenzahl
        action=next(i for i,a in enumerate(MODULE_ACTIONS) if a.kind=='place' and env.action_mask()[i])
        self.assertEqual(env.observation(),other.observation())
        env.step(action);other.step(action)
        self.assertEqual(public_effect(env),public_effect(other))


if __name__=='__main__':unittest.main()
