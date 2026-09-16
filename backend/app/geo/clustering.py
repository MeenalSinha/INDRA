"""
Spatial clustering using DBSCAN over report lat/lng, with a haversine metric
so eps is expressed in real kilometers rather than raw degrees. This is the
"127 reports -> 3 spatial clusters" step in the pipeline.
"""
import numpy as np
from sklearn.cluster import DBSCAN
from .. import config


def cluster_reports(reports: list):
    """
    reports: list of objects with .id, .latitude, .longitude
    Returns: dict {cluster_label: [report_ids]} — label -1 is noise
    (unclustered / standalone reports, kept as-is, never dropped).
    """
    usable = [r for r in reports if r.latitude is not None and r.longitude is not None]
    if not usable:
        return {}

    coords = np.radians([[r.latitude, r.longitude] for r in usable])
    eps_rad = config.CLUSTER_EPS_KM / 6371.0  # convert km to radians for haversine metric

    db = DBSCAN(
        eps=eps_rad,
        min_samples=max(1, config.CLUSTER_MIN_SAMPLES),
        metric="haversine",
    ).fit(coords)

    clusters: dict[int, list[int]] = {}
    for report, label in zip(usable, db.labels_):
        clusters.setdefault(int(label), []).append(report.id)
    return clusters
