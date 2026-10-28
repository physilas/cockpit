"""Single-role information-state UCT with a fixed observation-limited partner.

The searching role may improve several decisions within a round. The partner
always follows its blueprint; it is never optimized using the root's private
hand. This avoids a cooperative determinization's privileged partner choices.
The IID root prior and independent two-role online search are approximations;
this implementation does not claim the SPARTA policy-improvement theorem.
"""
from dataclasses import dataclass, field
import hashlib
import json
import math
import time

from .belief_simulator import BeliefSimulator, simulation_step
from .rollout_search import candidates, round_value
from .safety_guard import ShieldedBlueprint


@dataclass
class Edge:
    visits: int = 0
    total: float = 0.

    @property
    def mean(self):
        return self.total / self.visits if self.visits else 0.


@dataclass
class Node:
    actions: list
    edges: dict = field(default_factory=dict)
    visits: int = 0

    def __post_init__(self):
        self.edges = {action: Edge() for action in self.actions}


class InformationSearchAgent:
    def __init__(self, airport, blueprint, *, simulations=128, width=10,
                 max_seconds=2., exploration=.8, max_depth=12, minimum_visits=4):
        if (any(type(n) is not int or n < 1 for n in (simulations, width, max_depth, minimum_visits))
                or not math.isfinite(max_seconds) or max_seconds <= 0
                or not math.isfinite(exploration) or exploration <= 0):
            raise ValueError('Use bounded positive information-search settings.')
        self.airport = airport
        self.blueprint = ShieldedBlueprint(airport, blueprint)
        self.simulations, self.width = simulations, width
        self.max_seconds, self.exploration = max_seconds, exploration
        self.max_depth, self.minimum_visits = max_depth, minimum_visits
        self.last_report = {}

    @staticmethod
    def key(view):
        return json.dumps(view, sort_keys=True, separators=(',', ':'))

    def _choices(self, view, mask):
        key = self.key(view)
        if key not in self.choices:
            baseline, ranked = self.blueprint.rank(view, mask)
            self.choices[key] = baseline, candidates(view, ranked, baseline, self.width)
        return self.choices[key]

    def _policy(self, view, mask):
        key = self.key(view)
        if key not in self.policy:
            self.policy[key] = self.blueprint.select(view, mask)
        return self.policy[key]

    def _leaf(self, env, round_number):
        if env.done:
            return 1. if env.game.status == 'gewonnen' else -1.
        if env.game.aktuelle_runde != round_number:
            return round_value(env.view())
        return None

    def _default(self, env, round_number, deadline):
        for _ in range(96):
            result = self._leaf(env, round_number)
            if result is not None:
                return result
            if time.monotonic() >= deadline:
                return None
            simulation_step(env, self._policy(env.view(), env.action_mask()))
        return -1.  # A helper loop is a failed planning continuation.

    def _simulate(self, env, role, round_number, depth, deadline):
        result = self._leaf(env, round_number)
        if result is not None:
            return result
        if time.monotonic() >= deadline:
            return None
        if depth >= self.max_depth:
            return self._default(env, round_number, deadline)
        # Only this fixed blueprint decides for the simulated partner, using
        # that actor's permitted view. No partner search tree is constructed.
        if env.current_role != role:
            simulation_step(env, self._policy(env.view(), env.action_mask()))
            return self._simulate(env, role, round_number, depth, deadline)
        view, mask = env.view(), env.action_mask()
        key = self.key(view)
        new = key not in self.tree
        if new:
            _, actions = self._choices(view, mask)
            self.tree[key] = Node(actions)
        node = self.tree[key]
        unvisited = [action for action in node.actions if not node.edges[action].visits]
        if unvisited:
            action = unvisited[0]
        else:
            action = max(node.actions, key=lambda a: node.edges[a].mean + self.exploration *
                         math.sqrt(math.log(node.visits + 1) / node.edges[a].visits))
        simulation_step(env, action)
        value = (self._default(env, round_number, deadline) if new else
                 self._simulate(env, role, round_number, depth+1, deadline))
        if value is not None:
            node.visits += 1
            node.edges[action].visits += 1
            node.edges[action].total += value
        return value

    def select(self, view, mask):
        started = time.monotonic()
        self.tree, self.choices, self.policy = {}, {}, {}
        baseline, proposals = self._choices(view, mask)
        root_key = self.key(view)
        self.tree[root_key] = Node(proposals)
        seconds = self.max_seconds
        if 'realtime' in view['modules_state']['modules']:
            seconds = min(seconds, max(.01, (view['modules_state']['time_remaining']-3)/24))
        deadline = started + seconds
        seed = int.from_bytes(hashlib.sha256(root_key.encode()).digest()[:8], 'big')
        simulator = BeliefSimulator(self.airport, view)
        completed = 0
        for ordinal in range(self.simulations):
            if time.monotonic() >= deadline:
                break
            env = simulator.sample(seed+ordinal)
            value = self._simulate(env, view['role'], view['round'], 0, deadline)
            if value is None:
                break
            completed += 1
        root = self.tree[root_key]
        eligible = [action for action in proposals if root.edges[action].visits >= self.minimum_visits]
        chosen = baseline
        if root.edges[baseline].visits >= self.minimum_visits and eligible:
            best = max(eligible, key=lambda a: (root.edges[a].mean, a == baseline, root.edges[a].visits))
            if root.edges[best].mean > root.edges[baseline].mean + .05:
                chosen = best
        self.last_report = dict(baseline=baseline, chosen=chosen, simulations=completed,
            nodes=len(self.tree), seconds=time.monotonic()-started,
            values={str(a): dict(visits=e.visits, value=e.mean) for a, e in root.edges.items()},
            objective='round_survival_and_public_potential', belief='iid_remaining_partner_dice',
            partner='fixed_observation_limited_blueprint', approximate=True)
        return chosen
