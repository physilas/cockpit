import json
import shutil
import subprocess
import unittest

import build_pwa


class OfflinePackTests(unittest.TestCase):
    def test_generated_inventory_matches_all_files_and_hashes(self):
        saved = (build_pwa.WEB / "js/offline-assets.js").read_text()
        data = json.loads(saved.split(" = ", 1)[1].rstrip(";\n"))
        self.assertEqual(data, build_pwa.inventory(), "Run make build after app changes")

    def test_pack_deduplicates_weights_and_excludes_training_models(self):
        data = build_pwa.inventory()
        models = data["models"]
        assets = data["assets"]
        self.assertEqual(len(models), 5)
        self.assertEqual(len({model["url"] for model in models}), 4)
        self.assertEqual(len({asset["url"] for asset in assets}), len(assets))
        self.assertEqual({model["url"] for model in models},
                         {asset["url"] for asset in assets if asset["url"].startswith("models/")})
        self.assertLess(data["bytes"], 32_000_000)

    def test_runtime_uses_local_version_for_loader_and_packages(self):
        index = (build_pwa.WEB / "index.html").read_text()
        app = (build_pwa.WEB / "js/app.js").read_text()
        self.assertIn('src="vendor/pyodide/0.26.1/pyodide.js"', index)
        self.assertIn('indexURL: new URL("vendor/pyodide/0.26.1/", document.baseURI)', app)
        self.assertNotIn('src="https://cdn.jsdelivr.net/pyodide/', index)

    @unittest.skipUnless(shutil.which("node"), "Node required for worker tests")
    def test_worker_handles_offline_and_failed_downloads(self):
        subprocess.run(["node", "tests/offline-pack.cjs"], check=True, timeout=30,
                       cwd=build_pwa.WEB.parents[1])
