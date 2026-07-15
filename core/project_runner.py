import os


class ProjectRunner:

    def __init__(self, cnb_file):
        self.cnb_file = cnb_file

        file_name = os.path.splitext(os.path.basename(cnb_file))[0]
        self.base_dir = os.path.join(os.path.dirname(cnb_file), file_name)

        self.decoded_dir = os.path.join(self.base_dir, "decoded")
        self.plots_dir   = os.path.join(self.base_dir, "plots")
        self.reports_dir = os.path.join(self.base_dir, "reports")

    def prepare_folders(self):
        os.makedirs(self.decoded_dir, exist_ok=True)
        os.makedirs(self.plots_dir,   exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)