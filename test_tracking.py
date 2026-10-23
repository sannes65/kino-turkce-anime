import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server as s


class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file_patch = patch.object(s, "DATA_FILE", Path(self.tmp.name) / "data.json")
        self.file_patch.start()
        s.DB = copy.deepcopy(s.DEFAULT_DB)
        s.DB["settings"] = copy.deepcopy(s.DEFAULT_SETTINGS)
        self.handler = object.__new__(s.Handler)
        self.responses = []
        self.handler.send_json = lambda payload, status=200: self.responses.append((status, payload))
        self.media = {"anilistId": 999, "title": "Test anime", "status": "RELEASING"}

    def tearDown(self):
        self.file_patch.stop()
        self.tmp.cleanup()

    def add(self):
        self.handler.api_add({"media": self.media, "fetchEpisodes": False})
        return s.DB["animes"][0]

    def test_follow_does_not_queue_or_enable_downloads(self):
        with patch.object(s, "enqueue_fetch") as queue:
            a = self.add()
            queue.assert_not_called()
        self.assertFalse(a["autoFetch"]["enabled"])
        self.assertTrue(s.DB["lists"][a["id"]]["tracking"])

    def test_existing_add_still_queues(self):
        with patch.object(s, "enqueue_fetch", return_value=True) as queue:
            self.handler.api_add({"media": self.media})
        queue.assert_called_once()
        self.assertTrue(self.responses[-1][1]["queued"])

    def test_follow_deduplicates_changed_title_by_anilist_id(self):
        self.add()
        self.handler.api_add({"media": {**self.media, "title": "Other language"}, "fetchEpisodes": False})
        self.assertEqual(len(s.DB["animes"]), 1)
        self.assertEqual(self.responses[-1][1]["animeId"], "test-anime")

    def test_unfollow_survives_list_cleanup_and_reload(self):
        a = self.add()
        self.handler.api_list({"animeId": a["id"], "status": "", "tracking": False})
        s.load_db()
        self.assertFalse(s.DB["lists"][a["id"]]["tracking"])
        with patch.object(s, "anilist_query") as query:
            self.assertEqual(s.build_tracking()["items"], [])
            query.assert_not_called()

    def test_sparse_watched_episodes_and_undo(self):
        a = self.add()
        for n in (1, 3):
            self.handler.api_tracking_progress({"animeId": a["id"], "episode": n, "done": True})
        media = {"id":999,"title":{"english":"Test"},"status":"RELEASING", "airingSchedule":{"nodes":[{"episode":4,"airingAt":1}]}}
        with patch.object(s, "anilist_query", return_value={"Page":{"media":[media]}}):
            it = s.build_tracking()["items"][0]
        self.assertEqual((it["watched"],it["unwatched"],it["nextUnwatched"]), (2,2,2))
        self.handler.api_tracking_progress({"animeId": a["id"], "episode": 3, "done": False})
        self.assertFalse(s.DB["progress"][a["id"]+":3"]["done"])

    def test_finale_without_next_airing_is_counted(self):
        self.add()
        m = {"id":999,"status":"FINISHED","episodes":12,"title":{"english":"Test"}}
        with patch.object(s, "anilist_query", return_value={"Page":{"media":[m]}}):
            self.assertEqual(s.build_tracking()["items"][0]["aired"],12)

    def test_latest_airing_alias_wins_over_estimate(self):
        self.add()
        m = {"id":999,"status":"RELEASING","title":{"english":"Test"},
             "nextAiringEpisode":{"episode":8,"airingAt":9999999999}}
        result = {"Page":{"media":[m]}, "a999":{"airingSchedules":[{"episode":5,"airingAt":1}]}}
        with patch.object(s,"anilist_query",return_value=result):
            item = s.build_tracking()["items"][0]
        self.assertEqual(item["aired"],5)
        self.assertFalse(item["estimated"])

    def test_missing_history_labels_next_episode_inference(self):
        self.add()
        m = {"id":999,"title":{"english":"Test"},"nextAiringEpisode":{"episode":4,"airingAt":9999999999}}
        with patch.object(s,"anilist_query",return_value={"Page":{"media":[m]}}):
            item = s.build_tracking()["items"][0]
        self.assertEqual(item["aired"],3)
        self.assertTrue(item["estimated"])

    def test_schedule_bounds_rejected_before_network(self):
        for query in ("days=0", "days=15", "offset=57", "offset=-15", "days=abc"):
            self.handler.path = "/api/schedule?"+query
            with patch.object(s,"anilist_schedule") as schedule:
                self.handler.route_get()
                schedule.assert_not_called()
            self.assertEqual(self.responses[-1][0],400)

    def test_unknown_airing_stays_unknown_offline(self):
        self.add()
        with patch.object(s, "anilist_query", side_effect=OSError("offline")):
            r = s.build_tracking()
        self.assertTrue(r["warning"])
        self.assertIsNone(r["items"][0]["aired"])
        self.assertFalse(r["items"][0]["live"])

    def test_progress_invalid_requests_do_not_change_data(self):
        a = self.add()
        before = copy.deepcopy(s.DB)
        for ep in (0, -1, "1", True, None, 1.2, 100001):
            self.handler.api_tracking_progress({"animeId":a["id"],"episode":ep,"done":True})
            self.assertEqual(self.responses[-1][0],400)
        self.assertEqual(s.DB,before)

    def test_progress_unknown_anime_is_404(self):
        self.handler.api_tracking_progress({"animeId":"absent","episode":1,"done":True})
        self.assertEqual(self.responses[-1][0],404)

    def test_schedule_turkey_midnight_and_pagination_beyond_200(self):
        calls = []
        def query(q, v, ttl):
            calls.append(v)
            return {"Page":{"pageInfo":{"hasNextPage":v["page"] < 5}, "airingSchedules":[
                {"airingAt":v["from"]+1,"episode":v["page"],"media":{"id":v["page"],"type":"ANIME","title":{"english":"Test"}}},
                {"airingAt":v["from"]+1,"episode":1,"media":{"id":50,"type":"MANGA"}},
                {"airingAt":v["from"]+1,"episode":1,"media":{"id":51,"type":"ANIME","isAdult":True}},
                {"media":None}]}}
        with patch.object(s.time,"time",return_value=1792706400), patch.object(s,"anilist_query",side_effect=query):
            result = s.anilist_schedule()
        self.assertEqual(len(result),5)
        self.assertEqual((calls[0]["from"]+1+10800)%86400,0)
        self.assertEqual(calls[0]["to"]-(calls[0]["from"]+1),7*86400)

    def test_graphql_errors_are_not_cached_as_empty_success(self):
        s.API_CACHE.clear()
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self): return json.dumps({"errors":[{"message":"Rate limited"}]}).encode()
        with patch.object(s.urllib.request,"urlopen",return_value=Response()):
            with self.assertRaises(RuntimeError): s.anilist_query("query example",{})
        self.assertEqual(s.API_CACHE,{})

    def test_queries_with_same_prefix_do_not_share_cache(self):
        s.API_CACHE.clear()
        s.API_CACHE[json.dumps({"q":"x"*60+"one","v":{}},sort_keys=True)] = (s.time.time(), {"one":True})
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self): return b'{"data":{"two":true}}'
        with patch.object(s.urllib.request,"urlopen",return_value=Response()):
            self.assertEqual(s.anilist_query("x"*60+"two",{}),{"two":True})


if __name__ == "__main__":
    unittest.main(verbosity=2)
