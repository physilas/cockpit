import copy
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from ai.round_strategy_integrity import RUNTIME_SOURCES,runtime_metadata,validate_runtime


class RoundRuntimeIntegrityTests(unittest.TestCase):
    def fixture(self,folder):
        root=Path(folder);sources={}
        for name in RUNTIME_SOURCES:
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('measured '+name+'\n')
            sources[name]=hashlib.sha256(p.read_bytes()).hexdigest()
        weights={'format':1,'actor_bias':[.2,.3]}
        weights['release']={**runtime_metadata(weights,sources),'qualification_granted':True}
        return root,weights

    def test_changed_network_or_runtime_may_not_reuse_a_release(self):
        with TemporaryDirectory() as folder:
            root,weights=self.fixture(folder);validate_runtime(weights,root)
            altered=copy.deepcopy(weights);altered['actor_bias'][0]+=.1
            with self.assertRaisesRegex(ValueError,'parameters changed'):validate_runtime(altered,root)
            (root/'ai/round_strategy_constraints.py').write_text('different goal rules')
            with self.assertRaisesRegex(ValueError,'runtime changed'):validate_runtime(weights,root)

    def test_missing_qualification_or_source_binding_is_rejected(self):
        with TemporaryDirectory() as folder:
            root,weights=self.fixture(folder)
            weights['release']['qualification_granted']=False
            with self.assertRaises(ValueError):validate_runtime(weights,root)
            weights['release']['qualification_granted']=True
            weights['release']['runtime_sources'].pop('play_options.py')
            with self.assertRaisesRegex(ValueError,'Incomplete'):validate_runtime(weights,root)


if __name__=='__main__':unittest.main()
