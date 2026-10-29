"""Runs the (slow) analysis in a background thread and exposes its progress."""
import threading
import traceback

from fantasy_models.pipeline import run_analysis


class AnalysisState:
    def __init__(self, league, creds, my_team_id):
        self.league = league
        self.creds = creds            # stays on the server; never sent to the browser
        self.my_team_id = my_team_id
        self.cache = {}               # past seasons / downloaded NFL stats survive reloads
        self.lock = threading.Lock()
        self.thread = None

        self.status = "idle"          # idle | running | ready | error
        self.message = ""
        self.progress = 0
        self.error = None
        self.result = None            # last successful result stays visible if a reload fails

    def start(self, settings, refresh=True):
        """Kick off a run. Returns False if one is already in progress."""
        with self.lock:
            if self.status == "running":
                return False
            self.status, self.message, self.progress, self.error = "running", "Starting...", 0, None
        self.thread = threading.Thread(
            target=self._run, args=(dict(settings), refresh), daemon=True
        )
        self.thread.start()
        return True

    def _set_progress(self, message, percent):
        with self.lock:
            self.message, self.progress = message, percent

    def _run(self, settings, refresh):
        try:
            result, league = run_analysis(
                self.league, self.creds, settings, self.my_team_id,
                progress=self._set_progress, cache=self.cache, refresh=refresh,
            )
            with self.lock:
                self.result, self.league = result, league
                self.status, self.message, self.progress = "ready", "Up to date", 100
        except Exception as e:
            traceback.print_exc()
            with self.lock:
                self.status, self.error = "error", str(e) or e.__class__.__name__

    def snapshot(self):
        with self.lock:
            return {
                "status": self.status,
                "message": self.message,
                "progress": self.progress,
                "error": self.error,
                "has_result": self.result is not None,
            }
