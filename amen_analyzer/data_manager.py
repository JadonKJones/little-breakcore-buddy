import csv
import json


class DataManager:
    @staticmethod
    def save_analysis(onsets, filepath):
        """onsets: list of (time_in_seconds, label)"""
        data = {
            "onsets": [
                {"time": float(time), "label": label}
                for time, label in onsets
            ]
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_analysis(filepath):
        with open(filepath, "r") as f:
            data = json.load(f)
        return [(item["time"], item["label"]) for item in data["onsets"]]

    @staticmethod
    def export_csv(onsets, filepath):
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "label"])
            for time, label in onsets:
                writer.writerow([time, label])
