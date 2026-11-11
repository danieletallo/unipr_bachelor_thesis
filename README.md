# Cyclists' Efficiency and Behavior in Bologna

Bachelor's thesis project in Computer Science at the University of Parma, investigating cycling mobility using GPS traces from Bologna's **Bella Mossa (2017)** initiative.

The study compares observed journey times with minimum travel times estimated on a directed cycling network. It also examines travel direction compliance, cycling infrastructure, frequent origin-destination areas, and daily and hourly activity patterns.

## Processing pipeline

The Python research workflow covers:

1. **Data preparation:** select cycling activities from CSV files, discard missing coordinates, and normalize timestamps with pandas. The cycling subset contained approximately **72.4 million GPS points across 320,000 activities**.
2. **Map matching and segmentation:** use a local OSRM service to align GPS traces with the road network. Extract OpenStreetMap cycling nodes and edges with Pyrosm, build and simplify the graph with OSMnx, assign matched points to their nearest edges, and group consecutive points into segments.
3. **Segment enrichment:** calculate distance traveled, proportion of each edge covered, estimated full-edge travel time, cycling infrastructure flags, and travel direction compliance using OSM tags and GPS direction.
4. **Graph routing:** estimate edge weights from compliant observations using averages weighted by edge coverage. Construct a directed graph with cycling direction restrictions and use NetworkX's Dijkstra implementation to calculate minimum estimated travel times. Temporary endpoint nodes account for trips starting or ending partway along an edge.
5. **Analysis and visualization:** compare observed and estimated times by trip duration, aggregate direction compliance by road type, and explore spatial and temporal patterns with charts and maps.

## Key findings

- Dijkstra produced valid routes for **262,267 of 274,047 trips (95.7%)**.
- For trips under 15 minutes, median observed times were approximately **4.7-26% below** the modeled minimum; deviations became positive for longer trips.
- An estimated **19.5% of distance on secondary roads** was traveled against the permitted direction.

These findings depend on GPS quality, OSM tags, and estimated edge times; the routing baseline is a model rather than an absolute lower bound for individual cyclists.

## Technologies and repository scope

Python, pandas, NumPy, OSRM, OSMnx, Pyrosm, NetworkX, GeoPandas, Shapely, Matplotlib, and Folium.

This repository contains experimental scripts developed iteratively for the research questions. Some files contain incomplete code sections and assume intermediate datasets or local services. It is a research snapshot rather than production-ready software or a self-contained reproducible package.
