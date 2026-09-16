import logging
import datetime as dt
import csv
import json
from .adapters import DataSourceAdapter

log = logging.getLogger("indra.ingestion.dataset")

class DatasetBatchAdapter(DataSourceAdapter):
    """
    Adapter for processing public datasets in batch (CSV/JSON).
    Pipeline runs through the exact same ingest_report sequence.
    """
    @property
    def source_type(self) -> str:
        return "dataset"

    def fetch(self) -> list[dict]:
        raise NotImplementedError("Batch adapter uses process_file()")

    async def process_file(self, file_path: str, dataset_metadata: dict, db_session_factory):
        """
        Reads a CSV or JSON file and streams it into the pipeline.
        dataset_metadata should include: dataset_name, source, license
        """
        raw_reports = []
        if file_path.endswith('.csv'):
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_reports.append(self._map_csv_row(row, dataset_metadata))
        elif file_path.endswith('.json'):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    raw_reports.append(self._map_json_item(item, dataset_metadata))
        elif file_path.endswith('.parquet'):
            # Fallback if pandas isn't installed. For a real setup, `import pandas as pd`
            log.error("Parquet support requires pandas/pyarrow. Not implemented in this environment.")
            return

        db = db_session_factory()
        try:
            for raw in raw_reports:
                payload = self.normalize(raw)
                if self.validate(payload):
                    from .adapters import ingest_report
                    await ingest_report(db, payload)
        finally:
            db.close()
            
    def _map_csv_row(self, row: dict, metadata: dict) -> dict:
        return {
            "source": metadata.get("source", "Public Dataset"),
            "source_type": self.source_type,
            "text": row.get("text", row.get("description", "")),
            "timestamp": row.get("timestamp", dt.datetime.utcnow().isoformat()),
            "latitude": float(row["latitude"]) if row.get("latitude") else None,
            "longitude": float(row["longitude"]) if row.get("longitude") else None,
            "city": row.get("city"),
            "state": row.get("state"),
            "metadata": {
                "dataset_name": metadata.get("dataset_name"),
                "license": metadata.get("license"),
                "ingestion_time": dt.datetime.utcnow().isoformat(),
                "schema_version": "1.0",
                "raw_row": row
            }
        }

    def _map_json_item(self, item: dict, metadata: dict) -> dict:
        item.update({
            "source": metadata.get("source", "Public Dataset"),
            "source_type": self.source_type,
            "metadata": {
                "dataset_name": metadata.get("dataset_name"),
                "license": metadata.get("license"),
                "ingestion_time": dt.datetime.utcnow().isoformat(),
                "schema_version": "1.0"
            }
        })
        return item
