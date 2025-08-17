# Scene_Reconstruction
A simple pipeline for reconstruction with domestic scene.
## Citation / Acknowledgment

This project is inspired by and builds upon the work from **[Virtual Community (ViCo)](https://github.com/UMass-Embodied-AGI/Virtual-Community)**, developed by the Embodied AGI Lab at UMass Amherst. ViCo provides a physics-based multi-agent simulator and realistic 3D environments for research on embodied social intelligence.
They made a great job
We would like to acknowledge the original authors for their work and contributions.

## Introduction
Cause the domestic data is not accesible as the google's, We refactored the data of ViCo, and designed a pipeline for reconstruction
### Merge and align
First We need to get the single glb data and load them in data/scene_name folder and then we can use the script to merge them to a whole one.
### Creat road mask
The overpass-turbo data is accessible,so we can use the api to get the data of the road,in which way can we depart the road with the buildings.
### build terrain
Use the road data and ground data to build terrain.
### export height field 
Use the ground data and road data to export height field.
### bake terrain
Bake the terrain with the 3Dtiles texture.
### bake OSM buildings
Bake the OSM buildings with the 3Dtiles.
### fetch baidu streetview meta data
Fetch the meta data to get the best angle to projection.
### solve the cameras
Get the best angle to projection.
### Fetch the streetview
Download the streeviews with the best angle.
### inpaint the streetview
Detcetion, segment and inpainting.
### Projection
Project the streetview to the OSM.
### Combine
Combine the parts.

