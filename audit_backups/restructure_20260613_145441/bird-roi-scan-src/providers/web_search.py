# from bird_roi_scan.providers.ala import 
# from bird_roi_scan.providers.gbif import 
# from bird_roi_scan.providers.ebird import 
# from bird_roi_scan.providers.inaturalist import 

QUERY_TEMPLATES = [
    '"{common_name}" "{place}" bird',
    '"{scientific_name}" "{place}"',
    '"{common_name}" "{region}" Queensland',
    '"{common_name}" "South East Queensland"',
    '"{common_name}" "Darling Downs"',
    '"{common_name}" "Bundaberg"',
    '"{common_name}" "Goondiwindi"',
    '"{scientific_name}" "Queensland"',
]

ROI_TERMS = [
    "Bundaberg",
    "Gin Gin",
    "Childers",
    "Fraser Island",
    "Hervey Bay",
    "Gympie",
    "Maryborough",
    "Sunshine Coast",
    "Brisbane",
    "Ipswich",
    "Lockyer Valley",
    "Toowoomba",
    "Darling Downs",
    "Warwick",
    "Stanthorpe",
    "Goondiwindi",
    "South East Queensland",
    "SEQ",
]

BIRD_CONTEXT_TERMS = [
    "sighting",
    "observed",
    "recorded",
    "bird list",
    "checklist",
    "ebird",
    "atlas",
    "occurrence",
    "photographed",
    "spotted at",
    "seen at",
]