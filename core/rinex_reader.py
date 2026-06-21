import georinex as gr


class RinexReader:

    def __init__(self, obs_file):
        self.obs_file = obs_file
        self.obs = None

    def load(self):
        self.obs = gr.load(self.obs_file)
        return self.obs

    def get_times(self):
        return self.obs.time.values