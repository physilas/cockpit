import json
import random
import time
import unittest
from unittest.mock import patch
from backend import bridge
from backend.katalog import logbuch_katalog
from backend.saves import dump_game, load_game
from backend.spielplan import Spielplan
from backend.wuerfel import Wuerfel


class SaveTests(unittest.TestCase):
    def test_all_standard_routes_roundtrip_without_rng_changes(self):
        for route in logbuch_katalog()['scenarios']:
            with self.subTest(route=route['id']):
                game=Spielplan(route['engine_code'],faehigkeitskarten=['adaptation','control'][:route['ability_count']])
                game.starte_spiel();rng=random.getstate();before=game.zustand()
                restored,history,state=load_game(dump_game(game,[],rng));after=restored.zustand()
                for key in ('server_time_ms','zeit_verbleibend'):
                    before.pop(key,None);after.pop(key,None)
                self.assertEqual(before,after);self.assertEqual(state,rng);self.assertEqual(random.getstate(),rng)
                self.assertIs(restored.cockpit.landung,restored.landung)
                self.assertIs(restored.zusatz.spiel,restored)

    def test_placed_and_pending_dice_keep_object_identity(self):
        game=Spielplan('LOG_ATL_GREEN');game.starte_spiel()
        game.pilot_wuerfel[0].augenzahl=3;game.cockpit.ruder_pilot.platziere(game.pilot_wuerfel[0])
        w=Wuerfel('kopilot');w.augenzahl=4;w.quelle='intern'
        game.zusatz.offen=[{'rolle':'kopilot','wuerfel':w}]
        other,_,_=load_game(dump_game(game,[],random.getstate()))
        self.assertIs(other.cockpit.ruder_pilot.wuerfel,other.pilot_wuerfel[0])
        self.assertEqual(other.zusatz.offen[0]['wuerfel'].quelle,'intern')
        self.assertEqual(other.zusatz.offen[0]['wuerfel'].augenzahl,4)

    def test_bridge_save_restores_rng_and_undo(self):
        bridge.neues_spiel('LOG_YUL_GREEN')
        bridge._spiel.pilot_wuerfel[0].augenzahl=3
        self.assertTrue(bridge.platziere('pilot',0,'ruder')['ergebnis']['erfolg'])
        raw=bridge.spiel_speichern();rng=random.getstate();value=random.random()
        bridge.neues_spiel('LOG_LHR_GREEN');bridge.spiel_laden(raw)
        self.assertEqual(random.getstate(),rng);self.assertEqual(random.random(),value)
        self.assertTrue(bridge.rueckgaengig()['ergebnis']['erfolg'])
        self.assertTrue(bridge._spiel.cockpit.ruder_pilot.ist_frei())
        self.assertFalse(bridge._spiel.pilot_wuerfel[0].platziert)

    def test_realtime_restores_remaining_time_not_old_absolute_deadline(self):
        game=Spielplan('LOG_PBH_BLACK',faehigkeitskarten=['control','adaptation'])
        game.starte_spiel();game.zusatz.deadline=time.time()+20
        raw=dump_game(game,[],random.getstate());data=json.loads(raw)
        with patch('backend.saves.time.time',return_value=data['saved_at']+100):
            restored,_,_=load_game(raw)
            self.assertAlmostEqual(restored.zusatz.deadline-restored.zusatz.clock(),20,delta=.02)

    def test_unknown_type_cannot_replace_current_game(self):
        bridge.neues_spiel('LOG_YUL_GREEN');game=bridge._spiel
        data=json.loads(bridge.spiel_speichern());data['nodes'][0]['type']='os.system'
        with self.assertRaises(ValueError):bridge.spiel_laden(json.dumps(data))
        self.assertIs(bridge._spiel,game)

    def test_difficulty_two_and_three_start_without_reroll(self):
        for route in logbuch_katalog()['scenarios']:
            if route['difficulty'] not in ('red','black'):continue
            game=Spielplan(route['engine_code'],faehigkeitskarten=['adaptation','control'][:route['ability_count']])
            game.starte_spiel();self.assertEqual(game.neuwurf_plaettchen,0,route['id'])


if __name__=='__main__':unittest.main()
