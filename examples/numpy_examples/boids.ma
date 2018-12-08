//Maya ASCII 2018ff09 scene
//Name: boids.ma
//Last modified: Sat, Dec 08, 2018 05:39:49 AM
//Codeset: 1252
requires maya "2018ff09";
requires -nodeType "mPyNode" "mpynode_plugin.py" "1.0";
requires "stereoCamera" "10.0";
currentUnit -linear centimeter -angle degree -time ntsc;
fileInfo "application" "maya";
fileInfo "product" "Maya 2018";
fileInfo "version" "2018";
fileInfo "cutIdentifier" "201811122215-49253d42f6";
fileInfo "osv" "Microsoft Windows 8 Business Edition, 64-bit  (Build 9200)\n";
createNode transform -shared -name "persp";
	rename -uuid "6647A7F5-45F4-6532-1193-AF88F4D82293";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" -563.66836995956271 257.14217895396041 245.11622683626086 ;
	setAttr ".rotate" -type "double3" -23.738352729607566 -67.400000000000489 4.1381647055318943e-15 ;
createNode camera -shared -name "perspShape" -parent "persp";
	rename -uuid "4CA13B83-406C-BF5C-059E-E381E6AD21F1";
	setAttr -keyable off ".visibility" no;
	setAttr ".focalLength" 34.999999999999993;
	setAttr ".centerOfInterest" 690.43599872822097;
	setAttr ".imageName" -type "string" "persp";
	setAttr ".depthName" -type "string" "persp_depth";
	setAttr ".maskName" -type "string" "persp_mask";
	setAttr ".homeCommand" -type "string" "viewSet -p %camera";
createNode transform -shared -name "top";
	rename -uuid "5184A840-4DCB-299B-F9CE-DEB467F7E959";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 11.497324074707493 1000.1212636158023 14.386423133203204 ;
	setAttr ".rotate" -type "double3" -89.999999999999986 0 0 ;
createNode camera -shared -name "topShape" -parent "top";
	rename -uuid "BC8187F1-42D0-0B60-84E9-4BB29F5405B7";
	setAttr -keyable off ".visibility" no;
	setAttr ".renderable" no;
	setAttr ".centerOfInterest" 1022.0013355610982;
	setAttr ".orthographicWidth" 115.21441679039695;
	setAttr ".imageName" -type "string" "top";
	setAttr ".depthName" -type "string" "top_depth";
	setAttr ".maskName" -type "string" "top_mask";
	setAttr ".tumblePivot" -type "double3" 5.0992493995223285 -21.880071945296024 4.1785273623146839 ;
	setAttr ".homeCommand" -type "string" "viewSet -t %camera";
	setAttr ".orthographic" yes;
createNode transform -shared -name "front";
	rename -uuid "6C5294CB-4292-855F-0A70-A2945AF6F44F";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 0 0 1000.1 ;
createNode camera -shared -name "frontShape" -parent "front";
	rename -uuid "E6BEF314-4949-54A6-BFDA-8F82240242F4";
	setAttr -keyable off ".visibility" no;
	setAttr ".renderable" no;
	setAttr ".centerOfInterest" 1000.1;
	setAttr ".orthographicWidth" 30;
	setAttr ".imageName" -type "string" "front";
	setAttr ".depthName" -type "string" "front_depth";
	setAttr ".maskName" -type "string" "front_mask";
	setAttr ".homeCommand" -type "string" "viewSet -f %camera";
	setAttr ".orthographic" yes;
createNode transform -shared -name "side";
	rename -uuid "8AC7A00D-47CE-E79F-5ACB-48898772C217";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 1000.1 0 0 ;
	setAttr ".rotate" -type "double3" 0 89.999999999999986 0 ;
createNode camera -shared -name "sideShape" -parent "side";
	rename -uuid "979FBE01-4990-9CC9-A910-96AE65885F78";
	setAttr -keyable off ".visibility" no;
	setAttr ".renderable" no;
	setAttr ".centerOfInterest" 1000.1;
	setAttr ".orthographicWidth" 30;
	setAttr ".imageName" -type "string" "side";
	setAttr ".depthName" -type "string" "side_depth";
	setAttr ".maskName" -type "string" "side_mask";
	setAttr ".homeCommand" -type "string" "viewSet -s %camera";
	setAttr ".orthographic" yes;
createNode transform -name "BOIDS";
	rename -uuid "036556A3-4155-69C8-973F-F1846119277F";
createNode transform -name "boid0" -parent "BOIDS";
	rename -uuid "CA65DAD4-4E87-1ACD-C9DC-3F9BC2867DB6";
createNode mesh -name "boidShape0" -parent "boid0";
	rename -uuid "AC5DAE42-43D0-733D-154B-F68B401F35D4";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
createNode transform -name "boid1" -parent "BOIDS";
	rename -uuid "2D277E1D-4E0E-2A2A-A2A8-9F89E19DB1B2";
createNode mesh -name "boidShape1" -parent "boid1";
	rename -uuid "20DC3E71-4F58-F5BB-6FC7-9EB7E43F1CED";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid2" -parent "BOIDS";
	rename -uuid "90D1D1F9-4CC6-B658-8639-E09BE9CB5CC0";
createNode mesh -name "boidShape2" -parent "boid2";
	rename -uuid "35EBB9A0-46F1-31E2-CB55-38952710E792";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid3" -parent "BOIDS";
	rename -uuid "48D63541-423F-7A6D-2281-F78206C65EB0";
createNode mesh -name "boidShape3" -parent "boid3";
	rename -uuid "EB43A4AC-4AFA-9510-7677-14BF4D5D46D9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid4" -parent "BOIDS";
	rename -uuid "B52A71B9-4D2D-5CA5-AE23-C982C8F5A713";
createNode mesh -name "boidShape4" -parent "boid4";
	rename -uuid "7E3AA13E-4711-07B6-D599-58BBEA4C081E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid5" -parent "BOIDS";
	rename -uuid "05DD96CE-4C22-3BE9-6073-F691A40C3330";
createNode mesh -name "boidShape5" -parent "boid5";
	rename -uuid "C7F5B8B8-4FEB-C318-2074-4591689C684E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid6" -parent "BOIDS";
	rename -uuid "F969270C-4BE8-7CED-EEEA-3B96B260FE8E";
createNode mesh -name "boidShape6" -parent "boid6";
	rename -uuid "F41FC495-477E-99E1-C5F9-5584E263495F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid7" -parent "BOIDS";
	rename -uuid "C8139476-40A8-E901-5080-A7AD8676EA72";
createNode mesh -name "boidShape7" -parent "boid7";
	rename -uuid "F8EC8E36-4A18-6284-3A78-ACA9767EFBC4";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid8" -parent "BOIDS";
	rename -uuid "3AA5BBE5-4AA3-EB75-81D2-EF820C4D4DB2";
createNode mesh -name "boidShape8" -parent "boid8";
	rename -uuid "3D3FC457-4CD5-7B3E-2A06-C0809888E025";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid9" -parent "BOIDS";
	rename -uuid "C72ED69E-496B-2326-90EA-B09ECF95A6DE";
createNode mesh -name "boidShape9" -parent "boid9";
	rename -uuid "EF9D4EAD-4A5B-8FDE-5E15-CF80E09137B0";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid10" -parent "BOIDS";
	rename -uuid "AA803A1E-4567-80CF-048A-388B3E0EBC73";
createNode mesh -name "boidShape10" -parent "boid10";
	rename -uuid "426C7338-48F6-8886-27E9-ABBD9E92052C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid11" -parent "BOIDS";
	rename -uuid "4E89AFB3-4665-BE3B-6658-BD99FC8408DB";
createNode mesh -name "boidShape11" -parent "boid11";
	rename -uuid "184AFBAE-4A40-F69A-E04A-64B403CC1AFE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid12" -parent "BOIDS";
	rename -uuid "5CE853D0-47E8-54B6-C35B-88BB7AE40FBD";
createNode mesh -name "boidShape12" -parent "boid12";
	rename -uuid "CEC03F47-40FA-585D-4574-929C6CA3904B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid13" -parent "BOIDS";
	rename -uuid "5BF07FD8-4365-4290-A331-04AB7071A5D2";
createNode mesh -name "boidShape13" -parent "boid13";
	rename -uuid "366DD8B9-4AB5-4861-327C-32BD399AA75B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid14" -parent "BOIDS";
	rename -uuid "CAC96F27-4011-FE6E-7A0E-86B1BB2013BA";
createNode mesh -name "boidShape14" -parent "boid14";
	rename -uuid "E416ED5F-4EE4-8333-8D22-00B7474C1F57";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid15" -parent "BOIDS";
	rename -uuid "22D48716-48CF-949F-7FED-2F80A7229931";
createNode mesh -name "boidShape15" -parent "boid15";
	rename -uuid "D7DAD41D-4BFF-F7EE-560B-17919E75DEF2";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid16" -parent "BOIDS";
	rename -uuid "0819E31E-4357-D274-F927-7C9118C6AA7C";
createNode mesh -name "boidShape16" -parent "boid16";
	rename -uuid "53695FD2-4880-24C9-AF35-4F96C374FD3D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid17" -parent "BOIDS";
	rename -uuid "B8ADF599-45B1-7F19-0168-C6B353493049";
createNode mesh -name "boidShape17" -parent "boid17";
	rename -uuid "F5ACA41D-42D5-E572-D8C9-9F8BEA85F37B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid18" -parent "BOIDS";
	rename -uuid "3197E6AE-4686-0C5B-494F-DB9D6A831A52";
createNode mesh -name "boidShape18" -parent "boid18";
	rename -uuid "1B6C6CCD-4786-6636-5442-A39D0801BF30";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid19" -parent "BOIDS";
	rename -uuid "EBC8F0AC-4010-AA13-2696-71AE47B15B0F";
createNode mesh -name "boidShape19" -parent "boid19";
	rename -uuid "686E5749-4F17-BA49-07C2-0B9AD2962632";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid20" -parent "BOIDS";
	rename -uuid "36326A24-4D2B-BA69-E368-3484E2FE5C1F";
createNode mesh -name "boidShape20" -parent "boid20";
	rename -uuid "3E019292-4FEA-0665-33AE-F0AD332679F9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid21" -parent "BOIDS";
	rename -uuid "770E848B-414A-031B-1A09-EBBBECAF06D5";
createNode mesh -name "boidShape21" -parent "boid21";
	rename -uuid "2ABA6C94-48D0-0AFE-BA11-95AF64CE11C5";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid22" -parent "BOIDS";
	rename -uuid "D9E0B73A-4C08-69FC-345D-8A82E1785573";
createNode mesh -name "boidShape22" -parent "boid22";
	rename -uuid "0EDDCA7B-4B4D-1F65-7B4D-CAAB2B7A3B36";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid23" -parent "BOIDS";
	rename -uuid "BCCAB5DE-4175-EB92-9873-A7AEC047B53D";
createNode mesh -name "boidShape23" -parent "boid23";
	rename -uuid "0B7B28F5-4EB7-DF2F-27E5-67885A9006F1";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid24" -parent "BOIDS";
	rename -uuid "999ED143-4219-9C40-450F-E993EF2D6270";
createNode mesh -name "boidShape24" -parent "boid24";
	rename -uuid "16F59887-47D8-0730-BBDF-5B9F32028E45";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid25" -parent "BOIDS";
	rename -uuid "88490356-42CE-F841-DA57-9FB834D968F1";
createNode mesh -name "boidShape25" -parent "boid25";
	rename -uuid "A98C7297-4E73-E8EB-A972-B98ECF16D8F6";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid26" -parent "BOIDS";
	rename -uuid "5456449A-4969-4870-102F-F990D5D226BA";
createNode mesh -name "boidShape26" -parent "boid26";
	rename -uuid "B886C98C-4E6D-7D00-DFD9-DB97CE4E74B5";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid27" -parent "BOIDS";
	rename -uuid "EDA35B83-41C7-09BE-EC77-D8BD179F7D61";
createNode mesh -name "boidShape27" -parent "boid27";
	rename -uuid "FCD581C7-4B32-52BC-5B50-E29E2F727087";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid28" -parent "BOIDS";
	rename -uuid "13EBF63F-4C09-9BCC-A507-7D8264D4D815";
createNode mesh -name "boidShape28" -parent "boid28";
	rename -uuid "549C6C64-4342-012B-E888-DD826A197357";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid29" -parent "BOIDS";
	rename -uuid "F628CDA8-498F-1FB0-6598-C0ABB0E4CFC3";
createNode mesh -name "boidShape29" -parent "boid29";
	rename -uuid "6DDB89E6-49CD-E837-F1A0-048B403F04B9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid30" -parent "BOIDS";
	rename -uuid "864D79F3-4CB9-A34D-4710-329B8B0ED9C0";
createNode mesh -name "boidShape30" -parent "boid30";
	rename -uuid "4F34DE18-4AAB-708D-F71E-8786305EEEAD";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid31" -parent "BOIDS";
	rename -uuid "5AC32279-47B9-3129-8240-7FBD0E6FD03D";
createNode mesh -name "boidShape31" -parent "boid31";
	rename -uuid "04543465-4516-EFA1-27A6-838920882255";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid32" -parent "BOIDS";
	rename -uuid "DE99EDD5-48FE-C9E2-E8F1-A2B164676C1D";
createNode mesh -name "boidShape32" -parent "boid32";
	rename -uuid "644E0462-44F8-4198-C881-F2978BB027D6";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid33" -parent "BOIDS";
	rename -uuid "92B159C3-477D-CE29-ABCE-BC84EF900A7D";
createNode mesh -name "boidShape33" -parent "boid33";
	rename -uuid "BA954AF6-4ACD-C2A8-9EC6-0DA87D655FFE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid34" -parent "BOIDS";
	rename -uuid "5CBFE6DF-4B1C-5119-7676-00B9E0FFC450";
createNode mesh -name "boidShape34" -parent "boid34";
	rename -uuid "5E154478-40C0-F5FD-19E3-31804E49901D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid35" -parent "BOIDS";
	rename -uuid "8AD91A95-484E-A9F1-1CA7-B981F9CF0698";
createNode mesh -name "boidShape35" -parent "boid35";
	rename -uuid "9964542B-49AA-5867-3096-9B87F6604ADC";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid36" -parent "BOIDS";
	rename -uuid "B9B30E83-44AF-0F0B-54DC-8CAD5C433E03";
createNode mesh -name "boidShape36" -parent "boid36";
	rename -uuid "F9EC3D28-4CD3-C9AF-0B7B-3898951D477B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid37" -parent "BOIDS";
	rename -uuid "0786DA02-4A6F-1562-632D-4F9C09F73683";
createNode mesh -name "boidShape37" -parent "boid37";
	rename -uuid "11B06DBF-4574-810A-E999-BFB02523022B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid38" -parent "BOIDS";
	rename -uuid "1375A616-4395-1ACE-9087-1299C4CC1C1F";
createNode mesh -name "boidShape38" -parent "boid38";
	rename -uuid "BA79FE54-4B61-A9E1-D726-36B9BC5A0863";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid39" -parent "BOIDS";
	rename -uuid "9020281E-449F-7499-DCDE-E49BB88220BA";
createNode mesh -name "boidShape39" -parent "boid39";
	rename -uuid "899B8E99-4C9A-BE9D-2400-A985050E649F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid40" -parent "BOIDS";
	rename -uuid "F580A677-4FCB-D10A-2D6A-A1BCA143BE1C";
createNode mesh -name "boidShape40" -parent "boid40";
	rename -uuid "7270F67B-4602-4A5B-115E-82B3C9AEB269";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid41" -parent "BOIDS";
	rename -uuid "F62A8C33-4334-4615-6B00-DAA38537CA8F";
createNode mesh -name "boidShape41" -parent "boid41";
	rename -uuid "6ABAA798-4968-3711-28A9-0CACCF551FC5";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid42" -parent "BOIDS";
	rename -uuid "8B206A04-4857-332F-C848-FEAB60E52694";
createNode mesh -name "boidShape42" -parent "boid42";
	rename -uuid "7F5A8701-410D-66F6-97A2-82A1D06855BE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid43" -parent "BOIDS";
	rename -uuid "A4AD3623-4D1B-E71A-2421-C0AB7A7A85AE";
createNode mesh -name "boidShape43" -parent "boid43";
	rename -uuid "DB0519E9-4D8E-53BF-06E0-CDBF548B031C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid44" -parent "BOIDS";
	rename -uuid "79180154-4A5D-AF8A-0212-B48C7BDA4452";
createNode mesh -name "boidShape44" -parent "boid44";
	rename -uuid "81A0C461-4CD2-77B0-0BE5-4BADCDE2BBF1";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid45" -parent "BOIDS";
	rename -uuid "B7B5F6BF-4623-8FF3-FAD5-2FBBF2340E18";
createNode mesh -name "boidShape45" -parent "boid45";
	rename -uuid "705D8306-4D42-310C-1BE4-53B12A4D70E1";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid46" -parent "BOIDS";
	rename -uuid "AAC08F64-4688-BEEC-88B6-AE9AEBB85408";
createNode mesh -name "boidShape46" -parent "boid46";
	rename -uuid "873AC964-493A-450D-6229-B9B5703CAD5D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid47" -parent "BOIDS";
	rename -uuid "977A95DE-47D5-F69E-0948-39B1BD25DA44";
createNode mesh -name "boidShape47" -parent "boid47";
	rename -uuid "DF46367D-425A-7BA7-64C2-CBB6FEA2A449";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid48" -parent "BOIDS";
	rename -uuid "A9089032-4455-91DF-7376-5F82CC163E76";
createNode mesh -name "boidShape48" -parent "boid48";
	rename -uuid "CA740644-4D9E-8DA7-83AE-43B6F1101DED";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid49" -parent "BOIDS";
	rename -uuid "02D7E301-4C99-D494-7990-F6A1A95A3797";
createNode mesh -name "boidShape49" -parent "boid49";
	rename -uuid "253F01E1-4264-7761-8C27-67A1B4AA87A7";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid50" -parent "BOIDS";
	rename -uuid "BC0E7730-41C1-F1B5-53CA-AD82CF632C47";
createNode mesh -name "boidShape50" -parent "boid50";
	rename -uuid "B57AF5EA-483C-F84F-AEDA-02AD130EC9E7";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid51" -parent "BOIDS";
	rename -uuid "E6AF752E-4A09-8232-7F3D-DEB2614B4164";
createNode mesh -name "boidShape51" -parent "boid51";
	rename -uuid "0CA1FB26-4FDD-8DC6-6E03-6087F038A084";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid52" -parent "BOIDS";
	rename -uuid "3151A742-41CD-8C80-350D-56AB6623CB9B";
createNode mesh -name "boidShape52" -parent "boid52";
	rename -uuid "FBCD60B0-422F-14BD-BCC8-11BB31E9AE2B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid53" -parent "BOIDS";
	rename -uuid "0B73C33B-4D29-378F-6721-3EB1A1B334B0";
createNode mesh -name "boidShape53" -parent "boid53";
	rename -uuid "8211FF37-4D49-99FD-7DD7-FA923D2A91D6";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid54" -parent "BOIDS";
	rename -uuid "DE499079-4935-BFEC-F97B-E59AEB9CC876";
createNode mesh -name "boidShape54" -parent "boid54";
	rename -uuid "4CB49950-48AB-339C-6F32-699BC7FE172B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid55" -parent "BOIDS";
	rename -uuid "E766A410-4F29-69A0-046A-C8A833702974";
createNode mesh -name "boidShape55" -parent "boid55";
	rename -uuid "81FBF3DD-40FD-0410-84CA-7AB6F2FF7B29";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid56" -parent "BOIDS";
	rename -uuid "BA896301-43AD-1BEC-F63E-158EFC9E44DA";
createNode mesh -name "boidShape56" -parent "boid56";
	rename -uuid "B994DA27-4925-55CE-2F18-D692EA8BA5E6";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid57" -parent "BOIDS";
	rename -uuid "78EE6A0A-4163-F267-1BE1-4AB036B5AD00";
createNode mesh -name "boidShape57" -parent "boid57";
	rename -uuid "CE9055BB-4F7E-EB15-A3FF-A793621ED89E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid58" -parent "BOIDS";
	rename -uuid "4F83CCB6-4984-F2FB-7868-9C8CAB916338";
createNode mesh -name "boidShape58" -parent "boid58";
	rename -uuid "01786BFA-4A75-AEB0-D0D2-80979F2431B9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid59" -parent "BOIDS";
	rename -uuid "6C069434-4103-6ACB-1B3C-DF9A2DFD2FDF";
createNode mesh -name "boidShape59" -parent "boid59";
	rename -uuid "7730271B-4046-FFFD-8652-4AAC1A805620";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid60" -parent "BOIDS";
	rename -uuid "ED193792-46C6-74BB-E0B5-43A6AF48CC8F";
createNode mesh -name "boidShape60" -parent "boid60";
	rename -uuid "FEE6AFEE-4659-1E99-2432-BCA17BD2CA77";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid61" -parent "BOIDS";
	rename -uuid "3B5E0FAA-46D2-D0CC-5267-1291620BD3B4";
createNode mesh -name "boidShape61" -parent "boid61";
	rename -uuid "113F3E4B-4F61-D8F9-9236-BAB1068E35E1";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid62" -parent "BOIDS";
	rename -uuid "DD72F1DB-408E-3E9F-F58B-079845E01484";
createNode mesh -name "boidShape62" -parent "boid62";
	rename -uuid "B31C85B6-47F5-C6ED-4055-5BB97F82AD4E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid63" -parent "BOIDS";
	rename -uuid "FF8E8E5C-4524-2ADA-4026-09B34EF4004E";
createNode mesh -name "boidShape63" -parent "boid63";
	rename -uuid "2F7C229F-495E-41D2-3B88-E6952E8EB998";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid64" -parent "BOIDS";
	rename -uuid "B10101B0-4AC6-D128-5CFF-CA8B63773C8C";
createNode mesh -name "boidShape64" -parent "boid64";
	rename -uuid "B5C619B2-4BA4-CADF-213D-3F927CAD19EF";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid65" -parent "BOIDS";
	rename -uuid "48A67AE7-4AFB-F8C1-3239-D18523509215";
createNode mesh -name "boidShape65" -parent "boid65";
	rename -uuid "EE767ED5-447C-F4C7-D19C-5880B0393857";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid66" -parent "BOIDS";
	rename -uuid "9590265D-4BE4-7D47-F6B3-64AC02ED80F3";
createNode mesh -name "boidShape66" -parent "boid66";
	rename -uuid "F363CCF9-4501-3D0F-B0E0-C8953CA871FE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid67" -parent "BOIDS";
	rename -uuid "3D134F76-41DC-B4CD-F97F-89ACBFE1B5D2";
createNode mesh -name "boidShape67" -parent "boid67";
	rename -uuid "CD68C0F4-4EFE-597E-3560-08A0DC35D7C2";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid68" -parent "BOIDS";
	rename -uuid "12DDA83A-4C62-15AC-02AF-3686CCDC23E1";
createNode mesh -name "boidShape68" -parent "boid68";
	rename -uuid "0293663C-471C-CEC7-86EF-5CA01708A377";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid69" -parent "BOIDS";
	rename -uuid "3079FF67-4803-DF67-EA64-B7BE510F6B6D";
createNode mesh -name "boidShape69" -parent "boid69";
	rename -uuid "97974FB4-4E16-A648-C2ED-D092163A65C0";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid70" -parent "BOIDS";
	rename -uuid "0412BA62-4078-B83E-1FBF-45B16D82F7A0";
createNode mesh -name "boidShape70" -parent "boid70";
	rename -uuid "46E04E84-4CE2-60C6-3D41-449D468F95EE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid71" -parent "BOIDS";
	rename -uuid "A89DDFC4-403D-3C0D-6AE8-7BAF1E1D309C";
createNode mesh -name "boidShape71" -parent "boid71";
	rename -uuid "0B4F3180-4B16-E501-8F11-34A560060C16";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid72" -parent "BOIDS";
	rename -uuid "8453F04A-470C-F060-AB77-E9BD164693C6";
createNode mesh -name "boidShape72" -parent "boid72";
	rename -uuid "BCC5E4A8-4DF7-5A6A-A138-279C85A9CB4A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid73" -parent "BOIDS";
	rename -uuid "6597AE9A-4789-E221-FE36-F4ACF8EF4ABA";
createNode mesh -name "boidShape73" -parent "boid73";
	rename -uuid "7025E79E-4863-2CF3-8680-C09D94B9640E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid74" -parent "BOIDS";
	rename -uuid "DA9484C4-491E-28EE-A74A-408905FD0CA5";
createNode mesh -name "boidShape74" -parent "boid74";
	rename -uuid "7EFAE18F-4AF9-A1A0-5406-4EA2C0FEFE67";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid75" -parent "BOIDS";
	rename -uuid "55BBAC93-4022-F1F3-AB3A-C8995B9B08DC";
createNode mesh -name "boidShape75" -parent "boid75";
	rename -uuid "55747382-4EA0-0206-51A3-F4847A63BE4B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid76" -parent "BOIDS";
	rename -uuid "BD5FDB88-4A29-77D8-55FF-FE92C5B2A766";
createNode mesh -name "boidShape76" -parent "boid76";
	rename -uuid "5AAE484A-4EAA-14BE-4FC6-6BAE36305E8F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid77" -parent "BOIDS";
	rename -uuid "2FDE20B0-43AC-5ADA-00A6-FFA17A66C333";
createNode mesh -name "boidShape77" -parent "boid77";
	rename -uuid "A40698BA-416A-E13F-46A1-81AC3D6116D0";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid78" -parent "BOIDS";
	rename -uuid "8EBD3B04-4A50-C444-3229-B992EE613BE6";
createNode mesh -name "boidShape78" -parent "boid78";
	rename -uuid "D11C1B4B-4B01-5CF5-14A5-A0A7B13B5606";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid79" -parent "BOIDS";
	rename -uuid "9E624520-42A7-6D71-9E32-A5AA8543958B";
createNode mesh -name "boidShape79" -parent "boid79";
	rename -uuid "D8D56AD8-4864-8E82-9E84-F38811A3F707";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid80" -parent "BOIDS";
	rename -uuid "765A6C7B-42FE-04E3-F7A0-0CB9096FEFF7";
createNode mesh -name "boidShape80" -parent "boid80";
	rename -uuid "1BB9B9B0-4401-D311-8D6C-9885516488C4";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid81" -parent "BOIDS";
	rename -uuid "EA782846-417D-BBF2-1704-CAA05B0D4871";
createNode mesh -name "boidShape81" -parent "boid81";
	rename -uuid "C1C238E7-41FA-1450-3A09-A7A7FD5B06AC";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid82" -parent "BOIDS";
	rename -uuid "A56A23E9-43BC-B2B0-CD59-33AD89DA6B53";
createNode mesh -name "boidShape82" -parent "boid82";
	rename -uuid "581F3DB5-46C8-E862-6FFD-AA9A78525975";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid83" -parent "BOIDS";
	rename -uuid "8EB32EAF-4671-20A9-2652-E6A26F0C1E6B";
createNode mesh -name "boidShape83" -parent "boid83";
	rename -uuid "2153AEE5-4419-B4E1-00FC-15949DAA6F1A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid84" -parent "BOIDS";
	rename -uuid "4DDD7D7E-48F7-4110-68B0-F195A26D05EF";
createNode mesh -name "boidShape84" -parent "boid84";
	rename -uuid "A9AA04F5-45F9-5EFA-9C6A-DCBA96EE6D6A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid85" -parent "BOIDS";
	rename -uuid "CFC3ECE6-46F8-54F1-F211-46923A4C2EB7";
createNode mesh -name "boidShape85" -parent "boid85";
	rename -uuid "3228320A-4E23-3B57-00C3-788BA55D486B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid86" -parent "BOIDS";
	rename -uuid "9CCB1DF2-41A8-4F41-87D4-DF8D7D09E647";
createNode mesh -name "boidShape86" -parent "boid86";
	rename -uuid "90A66026-489B-0962-2212-7EB8B840916D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid87" -parent "BOIDS";
	rename -uuid "77AA5F09-4373-1497-52F9-6496326C9BDD";
createNode mesh -name "boidShape87" -parent "boid87";
	rename -uuid "861F9900-44A3-F952-5DC5-BBAD3245B76B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid88" -parent "BOIDS";
	rename -uuid "221DBEC2-40D0-DD72-87BD-ED93FF9E7A04";
createNode mesh -name "boidShape88" -parent "boid88";
	rename -uuid "EF11B15F-406C-35D1-C220-8C9FD6B77766";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid89" -parent "BOIDS";
	rename -uuid "F02C4164-46C8-FBBD-6166-2DBC59D0C510";
createNode mesh -name "boidShape89" -parent "boid89";
	rename -uuid "B5395300-4308-4D85-D689-48A03348DF1D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid90" -parent "BOIDS";
	rename -uuid "BB45C207-44DB-094D-055E-178F8C0402BA";
createNode mesh -name "boidShape90" -parent "boid90";
	rename -uuid "043332A5-4772-845A-8FDF-C58D47630FF8";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid91" -parent "BOIDS";
	rename -uuid "A166D336-4499-3856-344E-8AB82FE805AC";
createNode mesh -name "boidShape91" -parent "boid91";
	rename -uuid "64D2CDF8-4F6D-610D-F9BC-A8B48C237E49";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid92" -parent "BOIDS";
	rename -uuid "AB2EAB14-4F13-9B2C-40FB-ECB6FFB7D8F8";
createNode mesh -name "boidShape92" -parent "boid92";
	rename -uuid "591E6AB7-4D55-EC65-DFC6-018F5828F48C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid93" -parent "BOIDS";
	rename -uuid "6FE8A0E8-4DA8-1213-67BE-78A092EB5831";
createNode mesh -name "boidShape93" -parent "boid93";
	rename -uuid "842B481D-4A7C-2089-41DB-1392A5EA668A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid94" -parent "BOIDS";
	rename -uuid "7FE2D7C3-4980-5E7D-6591-268D5C800B17";
createNode mesh -name "boidShape94" -parent "boid94";
	rename -uuid "1A1A2C7D-4CF5-394E-9288-8B8F37E2BF6F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid95" -parent "BOIDS";
	rename -uuid "C71C384F-4A36-4140-9828-5CA109CCA3C5";
createNode mesh -name "boidShape95" -parent "boid95";
	rename -uuid "36BD197A-4ACA-12D2-3CA9-49B05D12D443";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid96" -parent "BOIDS";
	rename -uuid "60CC6164-4D7C-8C45-E964-13844D37E959";
createNode mesh -name "boidShape96" -parent "boid96";
	rename -uuid "B9DC5319-47BF-FED7-CC98-F096D81B43A6";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid97" -parent "BOIDS";
	rename -uuid "BF21E920-49FD-B162-1256-788085C0E5B8";
createNode mesh -name "boidShape97" -parent "boid97";
	rename -uuid "B915FC6B-4DDA-0FEB-4B7E-3CA008D59961";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid98" -parent "BOIDS";
	rename -uuid "2F8763B1-447E-A7AC-2933-168036EA6E65";
createNode mesh -name "boidShape98" -parent "boid98";
	rename -uuid "DEBC2466-46CD-C52A-77CC-04BE4E25AC32";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid99" -parent "BOIDS";
	rename -uuid "55592B63-4A68-5824-37E4-7E99EFFAA862";
createNode mesh -name "boidShape99" -parent "boid99";
	rename -uuid "5C479D7D-4201-C9B0-128B-E6846DEB466C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid100" -parent "BOIDS";
	rename -uuid "B1227693-4957-9588-55C1-98AD98217FD0";
createNode mesh -name "boidShape100" -parent "boid100";
	rename -uuid "BF1BE710-4576-09A0-3DC1-32ACAFD3E950";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid101" -parent "BOIDS";
	rename -uuid "950586C9-40FB-780B-5EE7-DB9C432FC059";
createNode mesh -name "boidShape101" -parent "boid101";
	rename -uuid "EC034FF6-46B6-9DB5-48A0-448B6195B3B1";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid102" -parent "BOIDS";
	rename -uuid "3877D356-4A37-33A5-767E-0A846EEAEE19";
createNode mesh -name "boidShape102" -parent "boid102";
	rename -uuid "AEE07975-412D-88F5-5F1A-0D817C88C2D8";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid103" -parent "BOIDS";
	rename -uuid "0111EDA8-43F0-2B26-1146-9382B50FDB06";
createNode mesh -name "boidShape103" -parent "boid103";
	rename -uuid "2F773EBD-4935-1753-DC1C-E6AE4E508259";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid104" -parent "BOIDS";
	rename -uuid "BEC31AC0-4CAC-F720-CE5C-8D956E6F9BAA";
createNode mesh -name "boidShape104" -parent "boid104";
	rename -uuid "6B927E90-47A0-E6EF-57AD-24A52CDFD513";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid105" -parent "BOIDS";
	rename -uuid "EA2D8926-43D9-659B-E345-1C94DA0D5694";
createNode mesh -name "boidShape105" -parent "boid105";
	rename -uuid "705C84F8-411E-D7B6-A089-85B2C02FACEA";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid106" -parent "BOIDS";
	rename -uuid "D3DC9CB7-4CB2-1C87-3C48-96801310FA8E";
createNode mesh -name "boidShape106" -parent "boid106";
	rename -uuid "11CAA372-4533-E67B-48C2-788E41099E97";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid107" -parent "BOIDS";
	rename -uuid "44C23593-4E35-41D6-02BD-6FBC780C2EF3";
createNode mesh -name "boidShape107" -parent "boid107";
	rename -uuid "FFC33CAD-4B64-8CD1-FB0B-7480A3BC27CF";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid108" -parent "BOIDS";
	rename -uuid "9016B40F-4399-5D47-0E3A-BF8038F6CF22";
createNode mesh -name "boidShape108" -parent "boid108";
	rename -uuid "B64DE9CE-4495-FFC4-B5C7-B4A3528A76F3";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid109" -parent "BOIDS";
	rename -uuid "5DE3033E-477F-6228-A047-738098B8FDAA";
createNode mesh -name "boidShape109" -parent "boid109";
	rename -uuid "5A3E18D9-40F1-DEC8-03BF-B2A08F84502F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid110" -parent "BOIDS";
	rename -uuid "9EBF584C-4064-1C28-E9EC-EB81BD3459CA";
createNode mesh -name "boidShape110" -parent "boid110";
	rename -uuid "C8DAF359-4B4F-E9A7-36BA-A291E023ACFF";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid111" -parent "BOIDS";
	rename -uuid "15F522C1-4A8D-7382-32EB-73A75760B13F";
createNode mesh -name "boidShape111" -parent "boid111";
	rename -uuid "B85DD7DB-4F0A-31BA-1AC4-67851D337EF8";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid112" -parent "BOIDS";
	rename -uuid "D148FFBA-44F3-BC44-A84F-F4835D7A2234";
createNode mesh -name "boidShape112" -parent "boid112";
	rename -uuid "41DDBFB6-4FDA-5AC5-EFD7-018A2D9E8C10";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid113" -parent "BOIDS";
	rename -uuid "6ECC4D14-451C-E783-FCBF-0BB8D250599E";
createNode mesh -name "boidShape113" -parent "boid113";
	rename -uuid "4EAD88E1-4A12-1DC1-52F5-E19EF3C5A771";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid114" -parent "BOIDS";
	rename -uuid "A35E5106-4572-F9E2-D451-968E2468A9C6";
createNode mesh -name "boidShape114" -parent "boid114";
	rename -uuid "A2BDE250-414E-0EED-8435-AAB4052B3CEC";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid115" -parent "BOIDS";
	rename -uuid "4EFD869D-4EE7-24BB-E9CC-77A4A01B31C7";
createNode mesh -name "boidShape115" -parent "boid115";
	rename -uuid "DE8F952E-45CF-9300-D766-6783720BA1CE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid116" -parent "BOIDS";
	rename -uuid "F0579ED4-44DA-DF61-F314-B2BCB987043B";
createNode mesh -name "boidShape116" -parent "boid116";
	rename -uuid "DBF062E9-4F85-14ED-DAA8-7299C0B164AD";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid117" -parent "BOIDS";
	rename -uuid "CA18A4AE-4291-43CB-9A1D-B2BC26EC7DF4";
createNode mesh -name "boidShape117" -parent "boid117";
	rename -uuid "05DAD98D-4093-BB99-FAA8-7191789BDA1F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid118" -parent "BOIDS";
	rename -uuid "940CA73C-4889-BDCF-CB2F-88B8D0C09FE9";
createNode mesh -name "boidShape118" -parent "boid118";
	rename -uuid "71452519-43BD-DDEB-8DDC-0283F0463F31";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid119" -parent "BOIDS";
	rename -uuid "AC6C5E10-4B3F-CA4B-FFA5-DA9E729926FB";
createNode mesh -name "boidShape119" -parent "boid119";
	rename -uuid "40BFFD4F-4CE4-32A6-0B96-27AB51D383D7";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid120" -parent "BOIDS";
	rename -uuid "5E3E3359-4327-D0D1-EC23-CB8CB6140120";
createNode mesh -name "boidShape120" -parent "boid120";
	rename -uuid "0A67504B-4C43-F0C4-3EF6-CDAE38B33D0D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid121" -parent "BOIDS";
	rename -uuid "4A9AEB23-4B58-2B66-F987-D98F2004BE40";
createNode mesh -name "boidShape121" -parent "boid121";
	rename -uuid "43BB2810-49DD-1F2C-208C-94B6360AB9F5";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid122" -parent "BOIDS";
	rename -uuid "28BBC817-462F-C374-1A55-63886218B64C";
createNode mesh -name "boidShape122" -parent "boid122";
	rename -uuid "57947B14-48BF-D57D-EA0B-608B1D3B3864";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid123" -parent "BOIDS";
	rename -uuid "C70F41C9-4075-9DD1-D4AB-91B831E6557D";
createNode mesh -name "boidShape123" -parent "boid123";
	rename -uuid "AE0D844C-4547-1BFE-5ADB-CA9B8E1194E9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid124" -parent "BOIDS";
	rename -uuid "A0033294-43EC-34DC-6CAC-E89A0A9EC9C3";
createNode mesh -name "boidShape124" -parent "boid124";
	rename -uuid "241722C3-4A96-A6B0-B083-8C83F40BA53D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid125" -parent "BOIDS";
	rename -uuid "87BEF730-4D75-E644-3EBF-CD812CF214C5";
createNode mesh -name "boidShape125" -parent "boid125";
	rename -uuid "60E0F65B-4942-18D6-A8D9-079B979097EB";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid126" -parent "BOIDS";
	rename -uuid "1E5B654A-4EC9-B7E7-8FE0-D2A1C9F47CD8";
createNode mesh -name "boidShape126" -parent "boid126";
	rename -uuid "7406A1B9-41CF-6721-672C-3E86EAD77806";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid127" -parent "BOIDS";
	rename -uuid "32B0D70E-45AF-EAFE-23FE-7BADDF5E56B5";
createNode mesh -name "boidShape127" -parent "boid127";
	rename -uuid "B655680E-44E5-AC7F-633B-0591C2D21963";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid128" -parent "BOIDS";
	rename -uuid "75137D4B-41EB-CAD4-4BC6-9B8663EBC578";
createNode mesh -name "boidShape128" -parent "boid128";
	rename -uuid "4F0B5362-40E1-115C-2C58-5A9029556041";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid129" -parent "BOIDS";
	rename -uuid "1FA23A5E-4001-A41A-6542-DC971FBFAA9E";
createNode mesh -name "boidShape129" -parent "boid129";
	rename -uuid "E7F80764-4DE4-60B7-2E5B-B994239E1671";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid130" -parent "BOIDS";
	rename -uuid "E032B0E3-4294-56A0-0C27-FF96AE6EED3A";
createNode mesh -name "boidShape130" -parent "boid130";
	rename -uuid "B566AD2E-4F38-81B2-6EF1-C48C2517A9E9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid131" -parent "BOIDS";
	rename -uuid "D6CDFFD4-4951-C093-9063-8BA61E384864";
createNode mesh -name "boidShape131" -parent "boid131";
	rename -uuid "24EFA2F6-4A36-E650-5AAC-80AF878D4F43";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid132" -parent "BOIDS";
	rename -uuid "14DD6BD1-48D3-AE82-4A93-CFB9D41F7E4F";
createNode mesh -name "boidShape132" -parent "boid132";
	rename -uuid "A6825C4E-4A9A-CF46-01DF-69B0BB20D635";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid133" -parent "BOIDS";
	rename -uuid "F27CE686-409A-A297-0ECE-A88377153DCB";
createNode mesh -name "boidShape133" -parent "boid133";
	rename -uuid "6BB6C6B4-44F2-ABE5-BCE6-AA8F84C79087";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid134" -parent "BOIDS";
	rename -uuid "4AAE3A04-4337-4522-0BE1-85A8A26B01EB";
createNode mesh -name "boidShape134" -parent "boid134";
	rename -uuid "6D1F7DCF-4831-44E9-0BC3-E39302984001";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid135" -parent "BOIDS";
	rename -uuid "1CFEF918-4FB2-7258-05B9-858C2A2A2469";
createNode mesh -name "boidShape135" -parent "boid135";
	rename -uuid "F0FACF6D-4F04-B78E-160B-07831C1D5A95";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid136" -parent "BOIDS";
	rename -uuid "14261C48-47AF-81F2-04EB-FB870377C255";
createNode mesh -name "boidShape136" -parent "boid136";
	rename -uuid "B49FDF10-4727-DF88-919C-218A8E174070";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid137" -parent "BOIDS";
	rename -uuid "E88830EA-4164-5FA5-161F-BF9779883F43";
createNode mesh -name "boidShape137" -parent "boid137";
	rename -uuid "8828EA34-405F-E171-DC3E-909305D16AA4";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid138" -parent "BOIDS";
	rename -uuid "936A9789-49F2-4293-8FCC-C1910C4CAF42";
createNode mesh -name "boidShape138" -parent "boid138";
	rename -uuid "D28C9060-4126-5B45-A5DE-D697288433DA";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid139" -parent "BOIDS";
	rename -uuid "1F1B0071-4112-B750-064E-6783DFEA6D13";
createNode mesh -name "boidShape139" -parent "boid139";
	rename -uuid "6D239C35-4F77-DA09-872A-F2BD15E3DF7B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid140" -parent "BOIDS";
	rename -uuid "8860811A-4366-2BD7-B491-9EA15EF9F524";
createNode mesh -name "boidShape140" -parent "boid140";
	rename -uuid "F511444B-4ACA-ED83-323C-9287458790E9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid141" -parent "BOIDS";
	rename -uuid "478A73C5-4AD2-097B-8214-258F5C687DD7";
createNode mesh -name "boidShape141" -parent "boid141";
	rename -uuid "329F6B45-490C-0EC1-5668-42978D687DF9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid142" -parent "BOIDS";
	rename -uuid "1E935AB5-4343-21E5-8669-87900B4FB99A";
createNode mesh -name "boidShape142" -parent "boid142";
	rename -uuid "C83D9363-4527-3A9B-5A3F-2D9F25AE3CDB";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid143" -parent "BOIDS";
	rename -uuid "2608FFD4-4EA3-D818-0F75-4BB10D76F1EF";
createNode mesh -name "boidShape143" -parent "boid143";
	rename -uuid "806C84BB-4FA6-7AAF-1BEF-1AA308BDA13C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid144" -parent "BOIDS";
	rename -uuid "0F693742-451F-BB0D-6D0A-44B15804120B";
createNode mesh -name "boidShape144" -parent "boid144";
	rename -uuid "E309328D-46F3-EC1D-70FB-2FAB87CD1E29";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid145" -parent "BOIDS";
	rename -uuid "600EE657-4431-568C-F8B8-72A661854DE4";
createNode mesh -name "boidShape145" -parent "boid145";
	rename -uuid "4E90C05F-42F9-4F01-7D28-359BC6F22086";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid146" -parent "BOIDS";
	rename -uuid "08E48881-48FA-2501-7E20-80BBD52B58F6";
createNode mesh -name "boidShape146" -parent "boid146";
	rename -uuid "61A20DAA-4584-D086-F2A5-4F861E8797C6";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid147" -parent "BOIDS";
	rename -uuid "79914248-48FE-1004-773F-DCB3D169AAC5";
createNode mesh -name "boidShape147" -parent "boid147";
	rename -uuid "53BCEA04-4F62-5212-520E-D79F69B048D8";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid148" -parent "BOIDS";
	rename -uuid "85B22133-4085-8856-A2AB-E085465DC0DD";
createNode mesh -name "boidShape148" -parent "boid148";
	rename -uuid "999A7255-4899-7372-754D-8E80381367CA";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid149" -parent "BOIDS";
	rename -uuid "14F7CA3C-458F-05A7-42EC-A29BEEA490F4";
createNode mesh -name "boidShape149" -parent "boid149";
	rename -uuid "EAE62116-424D-DE8B-AA1B-36BF29FBF325";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid150" -parent "BOIDS";
	rename -uuid "B3B9F7A6-482E-472C-3603-7985FA35B54B";
createNode mesh -name "boidShape150" -parent "boid150";
	rename -uuid "E05AE565-41E7-2FCD-F891-358A6819062A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid151" -parent "BOIDS";
	rename -uuid "C8F8D8EC-46A3-0AE4-FB1B-559A9ABF612E";
createNode mesh -name "boidShape151" -parent "boid151";
	rename -uuid "CEEDDC88-4054-DBDB-14CE-4FB503D70514";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid152" -parent "BOIDS";
	rename -uuid "E162CF1D-488A-009D-4293-6BAEA54E8005";
createNode mesh -name "boidShape152" -parent "boid152";
	rename -uuid "1140DDC6-4ED7-47EC-B81E-DD8AC75EF936";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid153" -parent "BOIDS";
	rename -uuid "68F92B54-4BF4-7F76-6618-21A4D26F4795";
createNode mesh -name "boidShape153" -parent "boid153";
	rename -uuid "0AB59466-49BE-710A-F107-8D812AC5EAE4";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid154" -parent "BOIDS";
	rename -uuid "C327682F-4135-D0DB-3362-3D9DDCBD7402";
createNode mesh -name "boidShape154" -parent "boid154";
	rename -uuid "E155305E-4BFC-1B0E-1639-DE848FB7120D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid155" -parent "BOIDS";
	rename -uuid "AC8421D7-4E60-EC50-994D-70AF737A549F";
createNode mesh -name "boidShape155" -parent "boid155";
	rename -uuid "302B3CDF-4F52-E76D-7371-2DA0C61C8246";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid156" -parent "BOIDS";
	rename -uuid "1D1F0E60-4212-0388-7001-53B523AD197D";
createNode mesh -name "boidShape156" -parent "boid156";
	rename -uuid "C7A482DC-4E68-AE1B-B5DF-0DB2B7B6362A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid157" -parent "BOIDS";
	rename -uuid "B5BE2AE8-4C8B-E40B-0E04-8DA24529FAA5";
createNode mesh -name "boidShape157" -parent "boid157";
	rename -uuid "328751F2-481E-7942-E5AD-28934C794609";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid158" -parent "BOIDS";
	rename -uuid "1E5BA7CA-42B5-2675-543C-FA8F87F55B82";
createNode mesh -name "boidShape158" -parent "boid158";
	rename -uuid "184E73A5-408E-6155-D1DE-868EE70D48D8";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid159" -parent "BOIDS";
	rename -uuid "B4497077-4E42-86A6-3D77-33A3FB40AB68";
createNode mesh -name "boidShape159" -parent "boid159";
	rename -uuid "260CCA77-4823-DAF9-2C84-B087754E7A28";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid160" -parent "BOIDS";
	rename -uuid "37975E2A-4DE6-6C5C-0486-758C95AA30CA";
createNode mesh -name "boidShape160" -parent "boid160";
	rename -uuid "F8F3BB12-4FF0-934A-F556-EC99FAE6931F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid161" -parent "BOIDS";
	rename -uuid "3FAB210F-4159-578F-335C-78A59D11419F";
createNode mesh -name "boidShape161" -parent "boid161";
	rename -uuid "27C5EB68-45AA-FAB9-811E-EB8A2C1BD15B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid162" -parent "BOIDS";
	rename -uuid "C5AD0ED5-4047-3AEF-796B-6481298893C3";
createNode mesh -name "boidShape162" -parent "boid162";
	rename -uuid "82FCBDFC-4185-50B2-C979-7C8AB7D39FDF";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid163" -parent "BOIDS";
	rename -uuid "59907060-4FD5-A46E-B4F0-45BB6AF419E4";
createNode mesh -name "boidShape163" -parent "boid163";
	rename -uuid "BDBF2C7C-4166-69C9-377E-778515D4F32D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid164" -parent "BOIDS";
	rename -uuid "5F4A029A-4DAC-0CBE-1FB1-B6B0410203CF";
createNode mesh -name "boidShape164" -parent "boid164";
	rename -uuid "88E32F2A-4EFE-AE45-0F20-74AA4AA2D07B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid165" -parent "BOIDS";
	rename -uuid "CC631FC0-4A2B-9697-943A-8CB0525AAFBC";
createNode mesh -name "boidShape165" -parent "boid165";
	rename -uuid "2697E81A-4207-7BC9-7F2F-C3A82B2B797B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid166" -parent "BOIDS";
	rename -uuid "FEF0617B-4988-7D3D-0143-E28FC6BFFDCE";
createNode mesh -name "boidShape166" -parent "boid166";
	rename -uuid "99CF72CB-4F6B-74D6-B46A-108CAD305D24";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid167" -parent "BOIDS";
	rename -uuid "B1FD36BD-4BE2-9E08-37DD-0A825280DFEB";
createNode mesh -name "boidShape167" -parent "boid167";
	rename -uuid "B044D87B-447E-036C-786E-0C93B336212F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid168" -parent "BOIDS";
	rename -uuid "DFE2A37D-42F1-1A06-4CEA-D99F4710804F";
createNode mesh -name "boidShape168" -parent "boid168";
	rename -uuid "001A7F7C-4E16-2304-0536-59AF6B6F6BD7";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid169" -parent "BOIDS";
	rename -uuid "E0A5DEF3-4868-3841-F838-76B7E5CDF870";
createNode mesh -name "boidShape169" -parent "boid169";
	rename -uuid "D85B6DEC-4C85-B8B6-9309-129AD005E805";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid170" -parent "BOIDS";
	rename -uuid "10700E68-41A2-14DB-DB7F-8A9376919945";
createNode mesh -name "boidShape170" -parent "boid170";
	rename -uuid "B6969B0E-4E63-934E-C8B6-2A850ADEC9EE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid171" -parent "BOIDS";
	rename -uuid "9ADC21C6-4DF2-C0B2-68BE-9BB2424FE9E3";
createNode mesh -name "boidShape171" -parent "boid171";
	rename -uuid "384773AF-416F-D380-C125-AA9B9EDBF2C6";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid172" -parent "BOIDS";
	rename -uuid "F3D0C793-46A7-A702-FB08-918D81F707E5";
createNode mesh -name "boidShape172" -parent "boid172";
	rename -uuid "EFD15011-4ACF-790D-367C-7B80F880793D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid173" -parent "BOIDS";
	rename -uuid "9D225DCF-49EB-D542-AADA-A89B519D8706";
createNode mesh -name "boidShape173" -parent "boid173";
	rename -uuid "5B581866-4B25-A186-DDC0-CFA3FE8FC3AE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid174" -parent "BOIDS";
	rename -uuid "32A3CED2-4C2D-52E1-B8C9-69A2CAA44126";
createNode mesh -name "boidShape174" -parent "boid174";
	rename -uuid "FD554476-4F32-CE99-B2F3-7083BB15382F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid175" -parent "BOIDS";
	rename -uuid "A78ECF8F-46FC-88BE-7364-64BDB121C9C7";
createNode mesh -name "boidShape175" -parent "boid175";
	rename -uuid "5D4F27E7-4ACE-621D-BA02-2CA11F896596";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid176" -parent "BOIDS";
	rename -uuid "0749633C-4A59-36F8-BB81-DDA777286C54";
createNode mesh -name "boidShape176" -parent "boid176";
	rename -uuid "0D30780B-4916-71F2-9D6C-63A070CC1B14";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid177" -parent "BOIDS";
	rename -uuid "A076015C-4203-DB8F-A509-F19016A3476D";
createNode mesh -name "boidShape177" -parent "boid177";
	rename -uuid "46BE98BB-4470-40CB-4F14-C29860E81DFF";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid178" -parent "BOIDS";
	rename -uuid "0253DCB5-42BC-2C24-F679-8FA74ECBA43F";
createNode mesh -name "boidShape178" -parent "boid178";
	rename -uuid "8F7FFF78-40C3-6456-2735-5DB462B7CE6A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid179" -parent "BOIDS";
	rename -uuid "23EAC613-44C6-C6E7-4CE1-D892A2DFB6EE";
createNode mesh -name "boidShape179" -parent "boid179";
	rename -uuid "A3620210-4C5F-54C3-1759-57BDAB149989";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid180" -parent "BOIDS";
	rename -uuid "9FDC06B9-40D6-8BD9-7702-B0B09E75906F";
createNode mesh -name "boidShape180" -parent "boid180";
	rename -uuid "1DC29540-417E-1B25-7002-16935CDBF04A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid181" -parent "BOIDS";
	rename -uuid "B8B433CB-433E-FDA1-529C-CF9C3090B910";
createNode mesh -name "boidShape181" -parent "boid181";
	rename -uuid "75A8D3B9-4F5D-F9FF-9EFA-C2842B7FAA83";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid182" -parent "BOIDS";
	rename -uuid "8CB59F6B-45CF-635D-8F25-7E9AC3C57ACD";
createNode mesh -name "boidShape182" -parent "boid182";
	rename -uuid "499BEBA9-4630-F274-1258-7BA3D42CD038";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid183" -parent "BOIDS";
	rename -uuid "F4E8E4D9-4450-B286-4982-EF8445A2E43D";
createNode mesh -name "boidShape183" -parent "boid183";
	rename -uuid "7CC9AC44-4467-0393-B789-61B9E93B613D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid184" -parent "BOIDS";
	rename -uuid "7BF45D47-4F87-A9FA-340D-A899BD0C0BDA";
createNode mesh -name "boidShape184" -parent "boid184";
	rename -uuid "F2E06675-4272-B7C4-33F6-AF8A763635DB";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid185" -parent "BOIDS";
	rename -uuid "76CD2EDB-4ED7-D4A0-AAF6-6F9235C1568D";
createNode mesh -name "boidShape185" -parent "boid185";
	rename -uuid "5512F921-4C8F-BBDF-96A3-ADB9A774E71A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid186" -parent "BOIDS";
	rename -uuid "97805AD5-499D-59B1-D689-DBBF48CAF4DD";
createNode mesh -name "boidShape186" -parent "boid186";
	rename -uuid "6A9A3D46-40AA-66DD-4F0F-919F0C0FCA95";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid187" -parent "BOIDS";
	rename -uuid "C8C96EA1-4B91-C8BE-0B2B-C3BB16F07D68";
createNode mesh -name "boidShape187" -parent "boid187";
	rename -uuid "8E3F267C-4BF8-63FE-4D65-399CD697375C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid188" -parent "BOIDS";
	rename -uuid "FC4EDE03-45E3-07C2-B1EF-2FA2DA1833EB";
createNode mesh -name "boidShape188" -parent "boid188";
	rename -uuid "C050EE78-4F07-7AA1-74EC-2F85E5E09DF1";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid189" -parent "BOIDS";
	rename -uuid "FAC6C178-4FB9-64D7-E928-E3939BE248FB";
createNode mesh -name "boidShape189" -parent "boid189";
	rename -uuid "1BB27AD9-421E-91A0-42C0-58AEC545B741";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid190" -parent "BOIDS";
	rename -uuid "32F9163A-47EF-CDEA-12CA-FD8B0C88DEEE";
createNode mesh -name "boidShape190" -parent "boid190";
	rename -uuid "99D4E8F8-49D0-D328-27C4-CB8C84108DAD";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid191" -parent "BOIDS";
	rename -uuid "46DB063A-4F9F-66EB-D82C-8F92D649469D";
createNode mesh -name "boidShape191" -parent "boid191";
	rename -uuid "6FFD2A31-442F-1541-3C58-29876301168C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid192" -parent "BOIDS";
	rename -uuid "3AA0528B-4766-B5BF-0EE9-DBAAA70B9A28";
createNode mesh -name "boidShape192" -parent "boid192";
	rename -uuid "E22EE4F3-44F1-5ADC-CF8A-76B5618BD567";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid193" -parent "BOIDS";
	rename -uuid "C2EC2A7B-4F65-90C5-0B0A-EC912984C077";
createNode mesh -name "boidShape193" -parent "boid193";
	rename -uuid "4BEEAD84-48CB-23BE-0195-07B43B3A0C27";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid194" -parent "BOIDS";
	rename -uuid "794EA588-42E9-9BFA-5645-4C8563888608";
createNode mesh -name "boidShape194" -parent "boid194";
	rename -uuid "315324F7-44DC-F2A5-A604-E08348BF3F3E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid195" -parent "BOIDS";
	rename -uuid "0ECA6D98-4EB8-22F9-C280-4BB354EBBFF8";
createNode mesh -name "boidShape195" -parent "boid195";
	rename -uuid "CC1ADD8E-4CA4-F460-B4E4-E2A9A9DAD2DF";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid196" -parent "BOIDS";
	rename -uuid "8B804114-4A13-CE9E-D237-FFAB7D014842";
createNode mesh -name "boidShape196" -parent "boid196";
	rename -uuid "10061978-43B6-F24A-CA62-97BBF721BDBC";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid197" -parent "BOIDS";
	rename -uuid "531E3321-48FA-5DC2-DCCF-63878E0FE87D";
createNode mesh -name "boidShape197" -parent "boid197";
	rename -uuid "005F079F-40B8-3B0A-6005-5092A9AD9E37";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid198" -parent "BOIDS";
	rename -uuid "2C8020AF-496B-66E7-5E59-9282449BD909";
createNode mesh -name "boidShape198" -parent "boid198";
	rename -uuid "2A725AE3-4C45-4690-33FD-D1B924E30FD7";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid199" -parent "BOIDS";
	rename -uuid "83F5611E-47D5-30A5-9AB3-F78D6739E900";
createNode mesh -name "boidShape199" -parent "boid199";
	rename -uuid "6F0F3630-4600-6440-6784-769E80BEA529";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid200" -parent "BOIDS";
	rename -uuid "22266608-4F09-D703-80DF-0B8AE5419D35";
createNode mesh -name "boidShape200" -parent "boid200";
	rename -uuid "E7A12B55-4434-9772-0D7D-5A8C101917C4";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid201" -parent "BOIDS";
	rename -uuid "E4E3C6B1-4FAA-1B2F-2785-B785CFECA33A";
createNode mesh -name "boidShape201" -parent "boid201";
	rename -uuid "97798FF9-4E5A-96F9-C742-E3AAF8ADDEF5";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid202" -parent "BOIDS";
	rename -uuid "BCBB8A4D-4452-7F87-5ECD-B1AA78069793";
createNode mesh -name "boidShape202" -parent "boid202";
	rename -uuid "653045F5-4456-8366-205F-448491431BB8";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid203" -parent "BOIDS";
	rename -uuid "903D4AF0-462A-F4CE-5EC3-5D87C29360A3";
createNode mesh -name "boidShape203" -parent "boid203";
	rename -uuid "1D31FBFF-4300-7B7B-8B0A-D3A2DC8258E0";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid204" -parent "BOIDS";
	rename -uuid "955647BC-462E-3E06-816B-58BCAE454FB0";
createNode mesh -name "boidShape204" -parent "boid204";
	rename -uuid "D5E370D3-44C8-5EC7-EC33-CDACBC62EF85";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid205" -parent "BOIDS";
	rename -uuid "E617B873-4BCD-3D53-F944-E680C0B94838";
createNode mesh -name "boidShape205" -parent "boid205";
	rename -uuid "A4A6093D-4574-F336-690D-09B8454E80AE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid206" -parent "BOIDS";
	rename -uuid "E11413B4-43F7-410A-712D-67AE2FA0A1B7";
createNode mesh -name "boidShape206" -parent "boid206";
	rename -uuid "DDA6469A-4D21-6B4C-956A-34B8D55FD0F1";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid207" -parent "BOIDS";
	rename -uuid "2FED70D3-4938-8250-D24D-28AFAA764003";
createNode mesh -name "boidShape207" -parent "boid207";
	rename -uuid "23E687AE-41B8-A918-54FA-71B4A9370958";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid208" -parent "BOIDS";
	rename -uuid "7F67E6C1-4FF7-138B-D552-34A9FD2F3A21";
createNode mesh -name "boidShape208" -parent "boid208";
	rename -uuid "BE8D61AF-4C45-E22B-E543-50BC8F8E144A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid209" -parent "BOIDS";
	rename -uuid "B896BAA9-4DDB-D9D5-2BDA-6AA21A09D7C1";
createNode mesh -name "boidShape209" -parent "boid209";
	rename -uuid "B7D5411C-43FD-A9F9-B014-3AA61DA04D99";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid210" -parent "BOIDS";
	rename -uuid "EAFB27B7-4C9C-AD84-F84B-EDA7BD882079";
createNode mesh -name "boidShape210" -parent "boid210";
	rename -uuid "438613BD-4F72-FCFC-86E9-9EB8449F2787";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid211" -parent "BOIDS";
	rename -uuid "CA304484-4407-AD6B-C12E-A28D38D32D24";
createNode mesh -name "boidShape211" -parent "boid211";
	rename -uuid "138BFE68-4514-AFCE-C645-658EC619F9DA";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid212" -parent "BOIDS";
	rename -uuid "B02DA975-466A-5B85-E032-469AB0DC80FB";
createNode mesh -name "boidShape212" -parent "boid212";
	rename -uuid "BD075EAE-45F9-3CC7-D686-219FDD3061A4";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid213" -parent "BOIDS";
	rename -uuid "5BB98D60-420C-B61A-3FD1-0C8980DA3B0C";
createNode mesh -name "boidShape213" -parent "boid213";
	rename -uuid "AA387D78-4C79-789A-1FCE-5881B245DB3D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid214" -parent "BOIDS";
	rename -uuid "F33E3E95-4532-F06E-1D08-BF926D6E49F1";
createNode mesh -name "boidShape214" -parent "boid214";
	rename -uuid "F22E0141-4597-7B8B-587D-F8975D0EB63B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid215" -parent "BOIDS";
	rename -uuid "18C4ADE2-4DAB-07F9-892D-DC81143ECB9C";
createNode mesh -name "boidShape215" -parent "boid215";
	rename -uuid "851BA7EC-48A1-DD96-C9A2-E3BABAF18A62";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid216" -parent "BOIDS";
	rename -uuid "FDAB8028-4809-F0E1-3654-9B9CEB181908";
createNode mesh -name "boidShape216" -parent "boid216";
	rename -uuid "08FA13F4-46AE-0C57-3765-47AC4C06765E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid217" -parent "BOIDS";
	rename -uuid "78E2193E-437C-6867-F09B-83A5823B1A7A";
createNode mesh -name "boidShape217" -parent "boid217";
	rename -uuid "2B5E800E-4087-625F-B91D-619F7F2F0072";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid218" -parent "BOIDS";
	rename -uuid "9495EF32-42DC-710C-FDFA-548E31845F39";
createNode mesh -name "boidShape218" -parent "boid218";
	rename -uuid "0BBAA116-43AD-7D72-6709-1F925B4C2557";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid219" -parent "BOIDS";
	rename -uuid "DDB4B50D-4D99-3727-56A2-0E845AB59B13";
createNode mesh -name "boidShape219" -parent "boid219";
	rename -uuid "1AB6B96F-4AB0-A555-BAE7-BFA7A19CAFB6";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid220" -parent "BOIDS";
	rename -uuid "0F3E8FEE-4201-5F42-B77B-B69F6FC2763C";
createNode mesh -name "boidShape220" -parent "boid220";
	rename -uuid "096A2C33-4041-DDC8-88B2-FDB482A09BE6";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid221" -parent "BOIDS";
	rename -uuid "B225912D-465E-4DDA-650C-31BFA38F8290";
createNode mesh -name "boidShape221" -parent "boid221";
	rename -uuid "3DAAD02C-42DD-1553-0E27-D69698914E6E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid222" -parent "BOIDS";
	rename -uuid "842435B1-4FA3-F09E-63DA-00B26DFA9E76";
createNode mesh -name "boidShape222" -parent "boid222";
	rename -uuid "B3D2BADB-4DF4-B52A-D39E-1B97B93B03C9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid223" -parent "BOIDS";
	rename -uuid "B8FCFE3D-4415-DED5-FCD3-E59372EDA4B6";
createNode mesh -name "boidShape223" -parent "boid223";
	rename -uuid "C371076A-4165-35D6-6909-B0B51C064E31";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid224" -parent "BOIDS";
	rename -uuid "D5DB6072-4903-FE39-10B2-9FBB45A01F60";
createNode mesh -name "boidShape224" -parent "boid224";
	rename -uuid "37DB2503-4893-6DE6-0EA7-55B7A896DC56";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid225" -parent "BOIDS";
	rename -uuid "DECDC3FE-43BA-E0BB-B060-47B7AD08C39E";
createNode mesh -name "boidShape225" -parent "boid225";
	rename -uuid "AB88C64D-4A79-D96A-4367-E3939882A4AE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid226" -parent "BOIDS";
	rename -uuid "11E1F6AE-4F29-154A-30DF-E289983C0819";
createNode mesh -name "boidShape226" -parent "boid226";
	rename -uuid "E07DB1DE-473E-32BE-DEB5-97A2192AAABF";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid227" -parent "BOIDS";
	rename -uuid "5C21DB54-4513-27B7-C8C2-5C8FDA3386F1";
createNode mesh -name "boidShape227" -parent "boid227";
	rename -uuid "11D19154-45F5-23D6-0378-D1B24B639D19";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid228" -parent "BOIDS";
	rename -uuid "63B4F9CD-43F0-7C45-9702-18A9BD45A349";
createNode mesh -name "boidShape228" -parent "boid228";
	rename -uuid "CFBF2527-409E-E086-F28E-30A6349055EB";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid229" -parent "BOIDS";
	rename -uuid "909BE2F0-41E2-26B9-C97F-0293C5C0EBCB";
createNode mesh -name "boidShape229" -parent "boid229";
	rename -uuid "D6775A8B-4E6D-AFAC-E772-88AC0E52E8BA";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid230" -parent "BOIDS";
	rename -uuid "32ACB77B-4B81-4A23-B14F-DD8B8F8DDCA8";
createNode mesh -name "boidShape230" -parent "boid230";
	rename -uuid "7D6B954D-4238-3934-F3F8-F08A23792FF3";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid231" -parent "BOIDS";
	rename -uuid "11835FC5-4C24-679D-2211-C88FE9C120B0";
createNode mesh -name "boidShape231" -parent "boid231";
	rename -uuid "54DC981B-45E1-D8FB-23DB-8286606D6163";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid232" -parent "BOIDS";
	rename -uuid "060ABF7E-4A1B-89FC-C00A-C8AB17258268";
createNode mesh -name "boidShape232" -parent "boid232";
	rename -uuid "9AEF4733-4F07-809E-1481-55899E9E1EEC";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid233" -parent "BOIDS";
	rename -uuid "A6378068-4EEF-3475-8A50-5E9F136FBFFA";
createNode mesh -name "boidShape233" -parent "boid233";
	rename -uuid "777DFE17-455D-0ACA-08E1-B4A13790D326";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid234" -parent "BOIDS";
	rename -uuid "4E1C0399-4FA0-DBEB-E4D0-B1898C1205EF";
createNode mesh -name "boidShape234" -parent "boid234";
	rename -uuid "3D47DC93-4B3A-CF40-32DF-619D16FB7C75";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid235" -parent "BOIDS";
	rename -uuid "F4A35832-41B0-A680-6334-A1A2425001ED";
createNode mesh -name "boidShape235" -parent "boid235";
	rename -uuid "327592F2-4540-CC55-12AC-F08D697C5543";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid236" -parent "BOIDS";
	rename -uuid "83864B3A-4C44-9322-A24F-D4BD34508E8E";
createNode mesh -name "boidShape236" -parent "boid236";
	rename -uuid "495456F6-4C4D-094C-786E-6BAF41D3C373";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid237" -parent "BOIDS";
	rename -uuid "7D5AB677-46C9-22E9-5074-2FA455B696D9";
createNode mesh -name "boidShape237" -parent "boid237";
	rename -uuid "1762293C-48D8-27C5-3B1C-4C8B5213DF3A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid238" -parent "BOIDS";
	rename -uuid "DA97B8BB-4BBC-EC40-0F5B-91B64B53ABCB";
createNode mesh -name "boidShape238" -parent "boid238";
	rename -uuid "B66FC463-4884-A6AF-B0E5-A38C010EEF96";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid239" -parent "BOIDS";
	rename -uuid "EC2218CB-430C-0F98-4477-ADB01B127A26";
createNode mesh -name "boidShape239" -parent "boid239";
	rename -uuid "D4DFAE5E-474F-98E8-13AF-C6A20A1AF2DA";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid240" -parent "BOIDS";
	rename -uuid "CB14898D-45BA-32D4-75AA-5491DA48C82C";
createNode mesh -name "boidShape240" -parent "boid240";
	rename -uuid "93F2E59F-4E83-A3BE-EC64-C9BEBBFB4290";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid241" -parent "BOIDS";
	rename -uuid "664A235F-4EDD-C5D7-0D09-AB8841F5371C";
createNode mesh -name "boidShape241" -parent "boid241";
	rename -uuid "D7663EBC-4C16-D6C8-FD78-4B85B07CD2B9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid242" -parent "BOIDS";
	rename -uuid "F8CAFA78-441B-FCE3-AA0C-A7AA277FAEE5";
createNode mesh -name "boidShape242" -parent "boid242";
	rename -uuid "1A16755C-41EC-BD4B-3CCB-9CAD3D2D4B6F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid243" -parent "BOIDS";
	rename -uuid "FD7C394B-44B3-0AA2-68C5-999AD181C3F1";
createNode mesh -name "boidShape243" -parent "boid243";
	rename -uuid "9430C57A-4058-4739-7143-B78BA45AF6EE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid244" -parent "BOIDS";
	rename -uuid "436356E6-4BFE-79F9-89AB-36AF5E4605EC";
createNode mesh -name "boidShape244" -parent "boid244";
	rename -uuid "12908C03-410A-3EDE-B7FD-34AD19D20208";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid245" -parent "BOIDS";
	rename -uuid "E94810F1-4D87-17DC-2298-C0B390BD9326";
createNode mesh -name "boidShape245" -parent "boid245";
	rename -uuid "77882967-4E21-1BE9-E730-3684B4C79E3A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid246" -parent "BOIDS";
	rename -uuid "B3D182D3-434B-03B6-7B55-349AF970C0B9";
createNode mesh -name "boidShape246" -parent "boid246";
	rename -uuid "E27FAD65-440E-A9ED-B0A3-6697DD1B31DF";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid247" -parent "BOIDS";
	rename -uuid "F53FD7AC-4706-A7CE-6C35-3D93F3C1C42B";
createNode mesh -name "boidShape247" -parent "boid247";
	rename -uuid "BB7FF62E-48BA-7AA7-F652-9584761E043E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid248" -parent "BOIDS";
	rename -uuid "B3EC125F-4008-D532-2267-8D8709F68A1A";
createNode mesh -name "boidShape248" -parent "boid248";
	rename -uuid "CEF200A1-40D4-0253-72A4-D8A429D77809";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid249" -parent "BOIDS";
	rename -uuid "DA2C11DF-47C3-002E-1BB3-96A341804145";
createNode mesh -name "boidShape249" -parent "boid249";
	rename -uuid "3CC45690-4DAB-1E98-ACD1-76B4244CC909";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid250" -parent "BOIDS";
	rename -uuid "1B718E06-4682-E713-5C1B-35A6C1BE41AC";
createNode mesh -name "boidShape250" -parent "boid250";
	rename -uuid "BBBBE738-4FF1-F9FB-2FC9-28838772C5E0";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid251" -parent "BOIDS";
	rename -uuid "2E6E1A0A-4F42-5F1E-7006-2CA60BBC96C7";
createNode mesh -name "boidShape251" -parent "boid251";
	rename -uuid "EED587F6-48C2-739C-91BC-05B367DF93BD";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid252" -parent "BOIDS";
	rename -uuid "5155774C-48C4-BA86-516F-3EB2380000B8";
createNode mesh -name "boidShape252" -parent "boid252";
	rename -uuid "7F4289B1-44D4-7928-19BA-65828A03D715";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid253" -parent "BOIDS";
	rename -uuid "3AD05106-49DF-48A3-F73B-77A46B488DC4";
createNode mesh -name "boidShape253" -parent "boid253";
	rename -uuid "F4198BA5-46E4-ABCA-D0B5-AC99ABB51754";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid254" -parent "BOIDS";
	rename -uuid "9EFDEC62-4FF5-9795-4859-BD89A413F0A6";
createNode mesh -name "boidShape254" -parent "boid254";
	rename -uuid "33D6F686-4204-EB80-152B-24AF8B79810E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid255" -parent "BOIDS";
	rename -uuid "CA4D35A8-4C76-591D-D402-CF85E9B30479";
createNode mesh -name "boidShape255" -parent "boid255";
	rename -uuid "0E8C1C8B-48D7-4E61-FCA1-28A79A452EDA";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid256" -parent "BOIDS";
	rename -uuid "320659BD-47DC-BF24-1072-4F977B24E040";
createNode mesh -name "boidShape256" -parent "boid256";
	rename -uuid "0AA43D57-4220-51FC-57B4-C0AC79D126D1";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid257" -parent "BOIDS";
	rename -uuid "8A34232A-4C92-5949-39E8-73BAC0B8B836";
createNode mesh -name "boidShape257" -parent "boid257";
	rename -uuid "07183A45-417A-7002-5474-CBB84E48CF71";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid258" -parent "BOIDS";
	rename -uuid "DEFFC209-4A9B-531F-0C40-88B23ACCE170";
createNode mesh -name "boidShape258" -parent "boid258";
	rename -uuid "E9DE0314-4D3C-0F98-FDA7-64A4BEDB3ADF";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid259" -parent "BOIDS";
	rename -uuid "3FA017AE-42E1-66B4-33DF-6090BE560B51";
createNode mesh -name "boidShape259" -parent "boid259";
	rename -uuid "C28D1563-4EEC-18CF-52DE-B1B062219C1C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid260" -parent "BOIDS";
	rename -uuid "E11AC3B9-4924-E35C-2144-85BEB9E74F84";
createNode mesh -name "boidShape260" -parent "boid260";
	rename -uuid "EEE9AC7B-454E-0641-D829-8BB5D5261D97";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid261" -parent "BOIDS";
	rename -uuid "43161868-4C3F-0ECF-70E9-2594EC305B0D";
createNode mesh -name "boidShape261" -parent "boid261";
	rename -uuid "8EE3C840-4497-97E2-5633-3C84F3C636E3";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid262" -parent "BOIDS";
	rename -uuid "E45AFEDD-4B40-304C-8180-A89BD28352D5";
createNode mesh -name "boidShape262" -parent "boid262";
	rename -uuid "A00D20C7-4ABF-907A-6035-F1BFD00D7433";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid263" -parent "BOIDS";
	rename -uuid "5BDD52BF-4E3E-FC6D-4323-2CAB3545EA68";
createNode mesh -name "boidShape263" -parent "boid263";
	rename -uuid "3558282A-437A-2C56-36CE-E3A5501731E3";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid264" -parent "BOIDS";
	rename -uuid "72E7373C-46FF-8337-9BA0-3BBD27EB95BF";
createNode mesh -name "boidShape264" -parent "boid264";
	rename -uuid "188FF922-4730-05EB-57BE-49B639E54F95";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid265" -parent "BOIDS";
	rename -uuid "9866EA64-4799-3728-E39F-A8897AD0B210";
createNode mesh -name "boidShape265" -parent "boid265";
	rename -uuid "F931E6F6-4848-B793-511A-B1BC8A8AF001";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid266" -parent "BOIDS";
	rename -uuid "7E8C6DCE-4E69-CC3D-B2A5-CAA4D2154F30";
createNode mesh -name "boidShape266" -parent "boid266";
	rename -uuid "B58B2C6C-4A2C-58FC-3F79-558812D960E7";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid267" -parent "BOIDS";
	rename -uuid "2AD413FE-48B0-32DD-FBFA-80A48B2B798A";
createNode mesh -name "boidShape267" -parent "boid267";
	rename -uuid "8F7DE643-488B-8D70-BE39-F3A52F7BA035";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid268" -parent "BOIDS";
	rename -uuid "ECF2FE52-4941-2BF6-4D00-E98F2FAE040E";
createNode mesh -name "boidShape268" -parent "boid268";
	rename -uuid "57D706CE-4AC8-9B7C-F256-00A87BF00F45";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid269" -parent "BOIDS";
	rename -uuid "A7DE2B9F-4999-ECCA-858B-628985DE7C75";
createNode mesh -name "boidShape269" -parent "boid269";
	rename -uuid "7E6CC96F-4972-4EE1-83A3-68B42146D430";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid270" -parent "BOIDS";
	rename -uuid "80DB6D13-4C07-CA91-F70D-BC93600761DF";
createNode mesh -name "boidShape270" -parent "boid270";
	rename -uuid "6C4D3EFC-49E7-1482-7C03-55A830454F3B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid271" -parent "BOIDS";
	rename -uuid "C47782BE-4A53-9EF0-1583-6EBE4ADF8914";
createNode mesh -name "boidShape271" -parent "boid271";
	rename -uuid "F827F54C-4849-2CA4-882E-BB8FBFA363BD";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid272" -parent "BOIDS";
	rename -uuid "5F1B39EA-4D86-8B2C-2D53-1B8DD2567144";
createNode mesh -name "boidShape272" -parent "boid272";
	rename -uuid "A104F50E-469A-C31A-4B31-4AB423DFE832";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid273" -parent "BOIDS";
	rename -uuid "D24363FB-46AC-0149-A189-9D93B1D4327D";
createNode mesh -name "boidShape273" -parent "boid273";
	rename -uuid "E30C3C69-4D0E-48CC-55AE-5C86FF351528";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid274" -parent "BOIDS";
	rename -uuid "9B805657-4D1A-32EC-986D-BD8E4A4B0A3D";
createNode mesh -name "boidShape274" -parent "boid274";
	rename -uuid "4A5378EA-4BA3-A7A7-8E41-9DAFDB772538";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid275" -parent "BOIDS";
	rename -uuid "DD04DDA3-47C9-F133-3379-2180E4C242A8";
createNode mesh -name "boidShape275" -parent "boid275";
	rename -uuid "9F551A73-4A3D-AD94-988F-0797AD852205";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid276" -parent "BOIDS";
	rename -uuid "B539E0EA-4EFA-AA53-E417-9995D2B7B40B";
createNode mesh -name "boidShape276" -parent "boid276";
	rename -uuid "2195CFFE-4F5C-16F7-57F6-86B077C53216";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid277" -parent "BOIDS";
	rename -uuid "1281DAB8-48EB-6E18-EAE8-92B9A8F0CBC5";
createNode mesh -name "boidShape277" -parent "boid277";
	rename -uuid "822EB1A2-4C52-D5E6-0E65-5A8F8CD82B99";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid278" -parent "BOIDS";
	rename -uuid "7C898A1E-4F72-6772-54E8-7A93CE1D20AA";
createNode mesh -name "boidShape278" -parent "boid278";
	rename -uuid "1A1D0B55-472E-A3FF-21D2-50A743CDC88F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid279" -parent "BOIDS";
	rename -uuid "224C6D6B-4FCA-9321-979C-748B08832850";
createNode mesh -name "boidShape279" -parent "boid279";
	rename -uuid "ABA0054C-48ED-980A-F13E-FDB8E133E34A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid280" -parent "BOIDS";
	rename -uuid "19B21A79-461F-DB08-7280-03ACAA4E735C";
createNode mesh -name "boidShape280" -parent "boid280";
	rename -uuid "2E57FC26-49AE-E56A-049D-CAB4BDA91E50";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid281" -parent "BOIDS";
	rename -uuid "93BDB5FE-4BB8-4E9C-F972-0A9AF94C0A67";
createNode mesh -name "boidShape281" -parent "boid281";
	rename -uuid "1733CCDA-45E3-5A15-F7A5-4BA987985641";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid282" -parent "BOIDS";
	rename -uuid "CB567A14-431B-5C2A-6ED0-C4B8FF5899FF";
createNode mesh -name "boidShape282" -parent "boid282";
	rename -uuid "A078364C-470C-5534-5922-28A423F8B230";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid283" -parent "BOIDS";
	rename -uuid "42ACBCA9-43D9-46B8-2820-1092E4D03E30";
createNode mesh -name "boidShape283" -parent "boid283";
	rename -uuid "3A55BD28-4F8D-0948-33CD-CC822B435769";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid284" -parent "BOIDS";
	rename -uuid "E3801CE7-4AD9-CBA7-6DCF-D080F69D68C2";
createNode mesh -name "boidShape284" -parent "boid284";
	rename -uuid "2508B0DF-45C6-535F-FF39-E3A15315B50D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid285" -parent "BOIDS";
	rename -uuid "091101A2-468C-1AA5-6CF3-20B2E643BEB8";
createNode mesh -name "boidShape285" -parent "boid285";
	rename -uuid "33D9CAB1-4152-95A2-F974-B0A3B6D6546D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid286" -parent "BOIDS";
	rename -uuid "E83830B4-40F2-2AC4-DDDB-2099F6AF2D86";
createNode mesh -name "boidShape286" -parent "boid286";
	rename -uuid "FB74A1F2-424E-B7A5-497C-059A65FD4511";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid287" -parent "BOIDS";
	rename -uuid "241F4EA1-4800-07C7-8430-969A0D92911F";
createNode mesh -name "boidShape287" -parent "boid287";
	rename -uuid "A1BE545B-47D4-C8DD-5D03-67880E0A36C7";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid288" -parent "BOIDS";
	rename -uuid "93AF1E11-4093-F32F-2FE9-798F6258A061";
createNode mesh -name "boidShape288" -parent "boid288";
	rename -uuid "74AA60DA-4655-2824-270F-C099EA5D2D30";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid289" -parent "BOIDS";
	rename -uuid "F03ADF7F-4C92-AC82-D4DE-08A3B9592C36";
createNode mesh -name "boidShape289" -parent "boid289";
	rename -uuid "35C84DF8-4157-28AB-7383-14AE08B3E82C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid290" -parent "BOIDS";
	rename -uuid "F274889B-49BC-AA17-34A4-718C528AC070";
createNode mesh -name "boidShape290" -parent "boid290";
	rename -uuid "304C2BE2-45C3-0B04-D81C-EDB3865067E0";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid291" -parent "BOIDS";
	rename -uuid "8C9C974B-47BD-B6E7-BA40-99922B9BB2BA";
createNode mesh -name "boidShape291" -parent "boid291";
	rename -uuid "EDE57176-4791-8D93-75F9-989556296007";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid292" -parent "BOIDS";
	rename -uuid "186272B6-4E57-1640-53EE-468B6A4392AD";
createNode mesh -name "boidShape292" -parent "boid292";
	rename -uuid "775A60A1-4A5C-5506-F116-82A70225418A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid293" -parent "BOIDS";
	rename -uuid "44F5C878-4697-1751-19A9-B897763988BB";
createNode mesh -name "boidShape293" -parent "boid293";
	rename -uuid "B38E673E-4F34-E9A5-E11D-CAA1F12D6678";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid294" -parent "BOIDS";
	rename -uuid "9865A326-4CEA-9FBD-5BC4-F2BF9004C8CD";
createNode mesh -name "boidShape294" -parent "boid294";
	rename -uuid "245229C5-431A-6154-6F9E-EB88B2BA8E36";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid295" -parent "BOIDS";
	rename -uuid "F6DAF232-4B33-6888-F8F1-4BBE55E8A7C6";
createNode mesh -name "boidShape295" -parent "boid295";
	rename -uuid "DF45BD59-4E4A-4FC3-8A50-E4BEB3D85F08";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid296" -parent "BOIDS";
	rename -uuid "C3FC4860-447E-B130-066B-EFB8EC4239CE";
createNode mesh -name "boidShape296" -parent "boid296";
	rename -uuid "3FAA5DAB-440A-1279-81F8-A8A88E3933B2";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid297" -parent "BOIDS";
	rename -uuid "A043A31F-43A1-01A1-2107-DF9E53D79302";
createNode mesh -name "boidShape297" -parent "boid297";
	rename -uuid "D5701542-4CCB-F7E6-00BD-FAA52BCAFF0F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid298" -parent "BOIDS";
	rename -uuid "B8A75920-439B-6CEB-51A0-789C2FEF710F";
createNode mesh -name "boidShape298" -parent "boid298";
	rename -uuid "385A870C-42AB-44E7-1051-1A9331EB6AAC";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid299" -parent "BOIDS";
	rename -uuid "74B45BA6-43B6-B125-A6FC-60A5497B6DE4";
createNode mesh -name "boidShape299" -parent "boid299";
	rename -uuid "74A9EA37-4DC2-3213-DAB0-C28686B90746";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid300" -parent "BOIDS";
	rename -uuid "B242B656-4EAC-C283-F5E0-8EB5147E2E49";
createNode mesh -name "boidShape300" -parent "boid300";
	rename -uuid "852C4470-4222-F11C-D4EF-F5A1956F3434";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid301" -parent "BOIDS";
	rename -uuid "64C54B7B-4C3D-B0A1-D6E6-B0BB28807346";
createNode mesh -name "boidShape301" -parent "boid301";
	rename -uuid "AC2D2CBE-47C5-BB6B-48A9-5985F436FF19";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid302" -parent "BOIDS";
	rename -uuid "FE73FAAF-469A-542C-7AC5-D2AF1FA0B283";
createNode mesh -name "boidShape302" -parent "boid302";
	rename -uuid "246D2B3B-44CD-4B6D-8247-B298047EA349";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid303" -parent "BOIDS";
	rename -uuid "57DD3E69-45AF-434C-3BC7-2C8029BEAA55";
createNode mesh -name "boidShape303" -parent "boid303";
	rename -uuid "F8944DEF-4C3B-A223-A053-5FA355A8BCC5";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid304" -parent "BOIDS";
	rename -uuid "9A10CC43-4ED9-517A-3043-51A652DC01F5";
createNode mesh -name "boidShape304" -parent "boid304";
	rename -uuid "DF5C837C-4A13-8B48-D675-3E8AF02F0D2B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid305" -parent "BOIDS";
	rename -uuid "B90F1B19-49E4-041A-8DD7-D688BBF5D22C";
createNode mesh -name "boidShape305" -parent "boid305";
	rename -uuid "01B38640-44CF-6D6E-84C4-A0955EB989D1";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid306" -parent "BOIDS";
	rename -uuid "C2A76325-41BA-E648-C847-B5896CA4FC1F";
createNode mesh -name "boidShape306" -parent "boid306";
	rename -uuid "363C8C93-4F2B-82CD-BA12-CD8D78BBFDEE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid307" -parent "BOIDS";
	rename -uuid "CB1A24CF-4A4D-677A-44F1-08BC85C0B8C8";
createNode mesh -name "boidShape307" -parent "boid307";
	rename -uuid "722631FB-48A6-808C-F7AC-43968F7F1324";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid308" -parent "BOIDS";
	rename -uuid "09E512D8-4E29-199A-E9D5-27866E1C7430";
createNode mesh -name "boidShape308" -parent "boid308";
	rename -uuid "07E33C46-476D-C23D-BEE3-54A589BDEED2";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid309" -parent "BOIDS";
	rename -uuid "C4AE35EF-40BF-4FB8-C17A-5B874B5C05EF";
createNode mesh -name "boidShape309" -parent "boid309";
	rename -uuid "C7678A30-44FA-319B-28F6-6AB0D187605C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid310" -parent "BOIDS";
	rename -uuid "DD9811DF-48D7-78EF-F6D0-A6AD241D2364";
createNode mesh -name "boidShape310" -parent "boid310";
	rename -uuid "534E5D55-49BB-CA1E-3B65-10BA2FC95C8A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid311" -parent "BOIDS";
	rename -uuid "2C33B811-4F68-7AAD-0409-80AF633E99CF";
createNode mesh -name "boidShape311" -parent "boid311";
	rename -uuid "2AA9587D-4730-C5FC-DE6C-34B808A5266F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid312" -parent "BOIDS";
	rename -uuid "3EA591AA-47A8-229F-4B61-FC8419AA8733";
createNode mesh -name "boidShape312" -parent "boid312";
	rename -uuid "B9E82691-4CB4-0C38-DBCD-43B163037CA3";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid313" -parent "BOIDS";
	rename -uuid "EF2F2F0A-49B6-747E-7089-0BB8AC06CC40";
createNode mesh -name "boidShape313" -parent "boid313";
	rename -uuid "7C196EBA-4117-BCCE-9211-929FC5E9A73F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid314" -parent "BOIDS";
	rename -uuid "D8655FBD-4C0B-972D-50C6-B6925B56A768";
createNode mesh -name "boidShape314" -parent "boid314";
	rename -uuid "CA057FA3-4594-F744-3888-4A84A90C85F4";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid315" -parent "BOIDS";
	rename -uuid "73D1E147-4E75-AE6A-ABEB-FAA6F62B6584";
createNode mesh -name "boidShape315" -parent "boid315";
	rename -uuid "D1478BD7-400E-AA37-4621-5D8A9CE4A3E4";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid316" -parent "BOIDS";
	rename -uuid "2799732C-424A-A37B-9DD4-159C34919676";
createNode mesh -name "boidShape316" -parent "boid316";
	rename -uuid "C9168670-41F4-5CC7-95C2-8493B9C9AC8D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid317" -parent "BOIDS";
	rename -uuid "20CF6605-4955-605A-C5C2-1BA62E7B068D";
createNode mesh -name "boidShape317" -parent "boid317";
	rename -uuid "584BBC8E-40F1-A7F6-5819-108374B12CE8";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid318" -parent "BOIDS";
	rename -uuid "E10AA67A-4490-B7AD-6F8A-65AA0F0445EE";
createNode mesh -name "boidShape318" -parent "boid318";
	rename -uuid "C7D53896-406C-FD02-2094-A9A4E95C786E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid319" -parent "BOIDS";
	rename -uuid "1290609D-4E14-DD35-9C68-559153EA025D";
createNode mesh -name "boidShape319" -parent "boid319";
	rename -uuid "4AAA7F1B-4095-8C1C-3131-98A42A864B0C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid320" -parent "BOIDS";
	rename -uuid "BC958526-451B-94EA-EF71-B2A1445BFF55";
createNode mesh -name "boidShape320" -parent "boid320";
	rename -uuid "691ED515-4605-CD01-216E-72B54BA17F06";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid321" -parent "BOIDS";
	rename -uuid "D2B3F1F3-416B-787C-45BF-BC9F4C1818F3";
createNode mesh -name "boidShape321" -parent "boid321";
	rename -uuid "C69752DE-42CB-73E3-7331-D093804C9797";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid322" -parent "BOIDS";
	rename -uuid "8B1EECF3-4D7D-7446-A7C7-F0927DCF8B2C";
createNode mesh -name "boidShape322" -parent "boid322";
	rename -uuid "1F934EB3-4D82-B66B-4843-43935F1CF533";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid323" -parent "BOIDS";
	rename -uuid "E2B1A7A6-4AE8-153E-37DC-7991691C89B6";
createNode mesh -name "boidShape323" -parent "boid323";
	rename -uuid "B80B9805-4A97-EC4F-0C4C-3E9D6B9BCA5A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid324" -parent "BOIDS";
	rename -uuid "9329B237-4BF5-5AAD-EC85-C89998E40B63";
createNode mesh -name "boidShape324" -parent "boid324";
	rename -uuid "D0FDD8E2-45A8-E8C9-829B-90848A4CE4A9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid325" -parent "BOIDS";
	rename -uuid "95AF5C24-4B0E-5971-9C1D-DBA2FE3D9FD0";
createNode mesh -name "boidShape325" -parent "boid325";
	rename -uuid "7E6246D0-4F50-CEA6-067B-069E1A3F3524";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid326" -parent "BOIDS";
	rename -uuid "8FE038A0-4031-C592-2BF8-4B973535075D";
createNode mesh -name "boidShape326" -parent "boid326";
	rename -uuid "B115006F-482C-EEC5-1473-15871DF2624F";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid327" -parent "BOIDS";
	rename -uuid "26CA4829-4877-04FD-AC9D-D9BF392A9783";
createNode mesh -name "boidShape327" -parent "boid327";
	rename -uuid "711595C3-444D-0F86-B383-588976A06F8D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid328" -parent "BOIDS";
	rename -uuid "CFB8C672-487F-51FC-D69E-328DF4BEDD70";
createNode mesh -name "boidShape328" -parent "boid328";
	rename -uuid "06E42730-4BD3-ACF7-1E81-66B03F1655A9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid329" -parent "BOIDS";
	rename -uuid "EEA66C17-4CDB-71C0-4E25-51A5B46B72A0";
createNode mesh -name "boidShape329" -parent "boid329";
	rename -uuid "86B6E0A8-4209-6813-CD12-EDA8763B3D57";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid330" -parent "BOIDS";
	rename -uuid "5FF9422D-4C40-A701-BBB3-9484EBB1D121";
createNode mesh -name "boidShape330" -parent "boid330";
	rename -uuid "1B1DACF4-4C0E-0A89-160A-6DB973A65664";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid331" -parent "BOIDS";
	rename -uuid "75ADDF90-42AA-CAC9-F662-B48E8BA0354B";
createNode mesh -name "boidShape331" -parent "boid331";
	rename -uuid "810AEF25-4C9F-BADE-947E-9DBC24068425";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid332" -parent "BOIDS";
	rename -uuid "91B6A1BC-4DE0-2B35-2082-DC9F0FCB6FC0";
createNode mesh -name "boidShape332" -parent "boid332";
	rename -uuid "141A3EFE-499E-1CF7-FBFF-D4A9867B6A93";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid333" -parent "BOIDS";
	rename -uuid "ECEF874E-4A53-073A-F21B-9980F513657A";
createNode mesh -name "boidShape333" -parent "boid333";
	rename -uuid "BBB717CD-4557-DB51-BF3B-EBB6B7568346";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid334" -parent "BOIDS";
	rename -uuid "536F6381-4902-7B8C-12D6-C981B6EAC9DE";
createNode mesh -name "boidShape334" -parent "boid334";
	rename -uuid "CE95E796-4ABC-7C2E-D1B8-EE9A778269BF";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid335" -parent "BOIDS";
	rename -uuid "0596274C-4076-1341-F48A-5A886CC6423C";
createNode mesh -name "boidShape335" -parent "boid335";
	rename -uuid "AF6ED4A5-46A3-00DC-DD7C-4CB0F6F25752";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid336" -parent "BOIDS";
	rename -uuid "1F0EF71C-4052-08C3-4393-48AAED3B27C9";
createNode mesh -name "boidShape336" -parent "boid336";
	rename -uuid "F288B379-44D4-152F-4967-B4BC2B2979DB";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid337" -parent "BOIDS";
	rename -uuid "C8AA4C6B-4B10-E9A1-A441-63A1E9D08C25";
createNode mesh -name "boidShape337" -parent "boid337";
	rename -uuid "91D2ED8A-48CD-FB0B-07BE-EF99247B7692";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid338" -parent "BOIDS";
	rename -uuid "73C1E073-4420-63F0-0AEA-A7A2CC6A7BA9";
createNode mesh -name "boidShape338" -parent "boid338";
	rename -uuid "0BA6E2A5-481A-C111-17D2-7385D6D13B4C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid339" -parent "BOIDS";
	rename -uuid "4E130718-4882-AEAD-A8CC-50A7C8F124FE";
createNode mesh -name "boidShape339" -parent "boid339";
	rename -uuid "CABB1FDB-4DB1-F1A9-5F05-BA80FF4EAE93";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid340" -parent "BOIDS";
	rename -uuid "FBFEC8A9-4E72-3D1F-0F52-10A531885938";
createNode mesh -name "boidShape340" -parent "boid340";
	rename -uuid "0ABC434D-480C-460B-9EAB-48AA27E5F3FC";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid341" -parent "BOIDS";
	rename -uuid "A0E19709-4B9F-F725-9516-E09FAC9EF1AF";
createNode mesh -name "boidShape341" -parent "boid341";
	rename -uuid "A6928328-412D-DEE5-497C-3184B12E1FEF";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid342" -parent "BOIDS";
	rename -uuid "A5B6DC50-4AD7-704B-B76B-A0B6CA4E8659";
createNode mesh -name "boidShape342" -parent "boid342";
	rename -uuid "3612D749-4704-78CA-2B84-60813FD7C8F9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid343" -parent "BOIDS";
	rename -uuid "B93697C8-49A8-6DDC-8213-D5A9D149F314";
createNode mesh -name "boidShape343" -parent "boid343";
	rename -uuid "A6AB9636-4186-EE6A-A538-A481324A978A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid344" -parent "BOIDS";
	rename -uuid "912947F1-4C35-9081-C972-3180C44E0043";
createNode mesh -name "boidShape344" -parent "boid344";
	rename -uuid "D609CA98-4143-4FF1-E6CF-D7933564D6DE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid345" -parent "BOIDS";
	rename -uuid "C60ACD40-4F5E-B2FB-0905-BAB3A24223D5";
createNode mesh -name "boidShape345" -parent "boid345";
	rename -uuid "816E0031-4158-36AF-6FE0-E9A04BE02521";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid346" -parent "BOIDS";
	rename -uuid "19ED0BB0-406F-5415-E211-97BCE4A250E9";
createNode mesh -name "boidShape346" -parent "boid346";
	rename -uuid "0F5D54C7-4B3D-2E7E-8024-3287B34EA981";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid347" -parent "BOIDS";
	rename -uuid "59640FDA-4D10-3E7A-A26B-CDBCE5CDF4FE";
createNode mesh -name "boidShape347" -parent "boid347";
	rename -uuid "F4020C00-4BF4-7EFD-4EC0-3988A151F978";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid348" -parent "BOIDS";
	rename -uuid "F065D270-4FCF-7483-7067-09A387320E82";
createNode mesh -name "boidShape348" -parent "boid348";
	rename -uuid "1F92CA19-4598-54D1-93D1-D8AD48B17DEA";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid349" -parent "BOIDS";
	rename -uuid "7FA0EF5F-4284-0B76-4F05-CFA15AE647D8";
createNode mesh -name "boidShape349" -parent "boid349";
	rename -uuid "285BCFCB-424B-F13F-2D23-49AA4260B3FA";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid350" -parent "BOIDS";
	rename -uuid "93F3EDF2-451C-A98A-5935-8CB37CDB82CA";
createNode mesh -name "boidShape350" -parent "boid350";
	rename -uuid "09A58086-4354-53E7-F84C-3CB90A7AF042";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid351" -parent "BOIDS";
	rename -uuid "EC37863B-4337-F897-A37D-768312AC4C75";
createNode mesh -name "boidShape351" -parent "boid351";
	rename -uuid "B50A05C0-4C88-0F02-B4CC-54A5C4190ACC";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid352" -parent "BOIDS";
	rename -uuid "E20B0335-40DA-1434-7EC9-518EC3BB06E3";
createNode mesh -name "boidShape352" -parent "boid352";
	rename -uuid "DE523A29-4CBB-A119-4FCE-F9A2B897C898";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid353" -parent "BOIDS";
	rename -uuid "FCE16AC6-499A-BA16-DA62-FBA6DBCE65EB";
createNode mesh -name "boidShape353" -parent "boid353";
	rename -uuid "E3476436-4170-0D3B-B73E-D2B53B01538D";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid354" -parent "BOIDS";
	rename -uuid "B13269E3-431D-BADC-40CE-8FA0AEA9A8EE";
createNode mesh -name "boidShape354" -parent "boid354";
	rename -uuid "A328897C-4EF3-0CD2-CD4B-449CA636C0F8";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid355" -parent "BOIDS";
	rename -uuid "05EA6825-43D2-AEAB-32FE-26889947C1E6";
createNode mesh -name "boidShape355" -parent "boid355";
	rename -uuid "2DEE6ECC-4DB7-EB73-8BE6-2BB778E3F6E7";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid356" -parent "BOIDS";
	rename -uuid "38B19D49-4F09-0279-7285-8E9EB93FEBB3";
createNode mesh -name "boidShape356" -parent "boid356";
	rename -uuid "953E9827-4AC2-1A5F-EA26-719FC3381207";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid357" -parent "BOIDS";
	rename -uuid "D0792BB0-47DC-B358-A33D-E9A64FF3499E";
createNode mesh -name "boidShape357" -parent "boid357";
	rename -uuid "0533D2FD-43D9-19E7-EE42-A68896CBD1D9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid358" -parent "BOIDS";
	rename -uuid "B6DC6FE3-4A3D-3AE6-FEE8-4391B81F3AE7";
createNode mesh -name "boidShape358" -parent "boid358";
	rename -uuid "E8D719F8-48B6-11A1-2D97-B195EB9A62CC";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid359" -parent "BOIDS";
	rename -uuid "E9421F76-48FD-CB6F-9818-8B938F0F2833";
createNode mesh -name "boidShape359" -parent "boid359";
	rename -uuid "8ADE69D5-4489-556C-9829-DC867B7D22D1";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid360" -parent "BOIDS";
	rename -uuid "D76A6F32-426D-C62E-FA09-BAA66522DC66";
createNode mesh -name "boidShape360" -parent "boid360";
	rename -uuid "0F8242D9-4A9B-3B07-DDA2-F5999B137A6B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid361" -parent "BOIDS";
	rename -uuid "369F31BE-4E0F-2DFD-477A-1990F36A6ECE";
createNode mesh -name "boidShape361" -parent "boid361";
	rename -uuid "D723275B-47BA-224A-CA04-568CEE77F682";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid362" -parent "BOIDS";
	rename -uuid "FE4751D8-4112-19FB-7B9C-50962A2975C7";
createNode mesh -name "boidShape362" -parent "boid362";
	rename -uuid "31653DD2-43E1-3A51-A00A-E58FD37023B8";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid363" -parent "BOIDS";
	rename -uuid "35EE8124-4A89-41AC-E8E4-14A98D00A3C4";
createNode mesh -name "boidShape363" -parent "boid363";
	rename -uuid "8F64BCB0-4589-E1DA-F4FD-E380EB4DD24A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid364" -parent "BOIDS";
	rename -uuid "33206FB5-4BCE-0168-E2A0-C4AECED7D09F";
createNode mesh -name "boidShape364" -parent "boid364";
	rename -uuid "3B451CD8-4371-6E94-1DB2-6BBAE85F6738";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid365" -parent "BOIDS";
	rename -uuid "A9ED5BF4-4A25-7C33-8906-3E98F0057AE9";
createNode mesh -name "boidShape365" -parent "boid365";
	rename -uuid "EF5BAF59-4DC3-A710-6219-2E92ADD95EC9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid366" -parent "BOIDS";
	rename -uuid "CE0517F1-41AB-940D-8618-BCB32156DE3A";
createNode mesh -name "boidShape366" -parent "boid366";
	rename -uuid "876ADCD9-41E5-7749-2F50-16AF6C7EA1F5";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid367" -parent "BOIDS";
	rename -uuid "246CCBBB-4F04-2913-E2B6-73A5BE22813B";
createNode mesh -name "boidShape367" -parent "boid367";
	rename -uuid "72E5F9FC-454A-52D8-977A-EA942257E80E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid368" -parent "BOIDS";
	rename -uuid "FAB60AC8-43E2-95C8-C0E3-06ACB9E23A10";
createNode mesh -name "boidShape368" -parent "boid368";
	rename -uuid "CF87BB88-48F2-324A-6111-8BA6383F9BA7";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid369" -parent "BOIDS";
	rename -uuid "140BF37D-42E6-289C-89CA-BFA6177CB39A";
createNode mesh -name "boidShape369" -parent "boid369";
	rename -uuid "CDCEC6B8-451B-0477-8698-BFB1D653D385";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid370" -parent "BOIDS";
	rename -uuid "6611DA3E-4C78-5C50-6B91-60A55830DF0F";
createNode mesh -name "boidShape370" -parent "boid370";
	rename -uuid "3337A1A6-41C4-4D47-5E8F-F2AE3DA3E7C9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid371" -parent "BOIDS";
	rename -uuid "3DD4864C-4297-9233-6D44-B69A385DF1ED";
createNode mesh -name "boidShape371" -parent "boid371";
	rename -uuid "024798E6-49F7-2789-F404-17B9A69F552A";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid372" -parent "BOIDS";
	rename -uuid "CD426D2B-414B-58D9-CE91-31B979D91312";
createNode mesh -name "boidShape372" -parent "boid372";
	rename -uuid "6CF3CD7E-4AFB-E2CC-BA3E-82973D957E75";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid373" -parent "BOIDS";
	rename -uuid "A31E2E79-4435-B802-B1A4-B698DD6D187D";
createNode mesh -name "boidShape373" -parent "boid373";
	rename -uuid "223CFDA6-45C9-ECE1-3B76-78B06FAEDEB6";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid374" -parent "BOIDS";
	rename -uuid "A7BDA528-4D1E-6EB0-43B3-558A244F65D4";
createNode mesh -name "boidShape374" -parent "boid374";
	rename -uuid "7A4CBD23-4FBE-FF20-D1A1-DBBDD6015FAE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid375" -parent "BOIDS";
	rename -uuid "82D82732-4069-DAAC-58CA-AE8AEE22732C";
createNode mesh -name "boidShape375" -parent "boid375";
	rename -uuid "BAFCB12E-487F-9766-2F7D-0FA74E5987C1";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid376" -parent "BOIDS";
	rename -uuid "D19F4F29-4EAB-CB67-1E10-C6B6C8C35F78";
createNode mesh -name "boidShape376" -parent "boid376";
	rename -uuid "41FAF8F3-4FA2-1609-A6D3-C2BA21E03442";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid377" -parent "BOIDS";
	rename -uuid "89D238FD-433E-E60A-0C1D-588E2B467CC6";
createNode mesh -name "boidShape377" -parent "boid377";
	rename -uuid "51571B29-4A72-8E37-DD34-86B9F1E7B404";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid378" -parent "BOIDS";
	rename -uuid "555420EF-4BD7-3FFA-F660-ADB7D436ACE4";
createNode mesh -name "boidShape378" -parent "boid378";
	rename -uuid "1B96E1D3-4822-0431-42A6-0689C6D31E83";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid379" -parent "BOIDS";
	rename -uuid "2F4E3246-4612-A2B6-9E83-54AE490042B1";
createNode mesh -name "boidShape379" -parent "boid379";
	rename -uuid "206C0521-4D6B-6CED-00DA-80B8985F7825";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid380" -parent "BOIDS";
	rename -uuid "F450B86D-46C1-BBE4-947A-3B89076993FC";
createNode mesh -name "boidShape380" -parent "boid380";
	rename -uuid "D85F2A48-4A95-55C8-8076-53BD332CE6E5";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid381" -parent "BOIDS";
	rename -uuid "510A6F4F-402C-B4E4-090B-C89C41B42841";
createNode mesh -name "boidShape381" -parent "boid381";
	rename -uuid "4C66F2C4-45B1-04CC-7A23-059A0A11352B";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid382" -parent "BOIDS";
	rename -uuid "1B957684-46BE-03F4-BCA4-A0BAA802D87C";
createNode mesh -name "boidShape382" -parent "boid382";
	rename -uuid "E9E19001-4A64-0B04-0B7C-489C5E2E7EE6";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid383" -parent "BOIDS";
	rename -uuid "D798056B-482E-377E-F814-6CA8EAA0457C";
createNode mesh -name "boidShape383" -parent "boid383";
	rename -uuid "6254F0E7-45C0-DE2D-0950-5F87C039E3D0";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid384" -parent "BOIDS";
	rename -uuid "C7E93FE9-43DD-2130-CE37-10AB5D880545";
createNode mesh -name "boidShape384" -parent "boid384";
	rename -uuid "B2E88CF7-4354-71C7-FF1F-53B6362EBB3E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid385" -parent "BOIDS";
	rename -uuid "6298506E-479F-E9C7-0F30-0F9EB8EE2C17";
createNode mesh -name "boidShape385" -parent "boid385";
	rename -uuid "FD836988-4557-8A9D-837C-0D8555B14F30";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid386" -parent "BOIDS";
	rename -uuid "BF382572-44D4-A525-C6BB-49A2CBAAC23A";
createNode mesh -name "boidShape386" -parent "boid386";
	rename -uuid "FD3A8943-403A-EBA7-5FEB-B6BAD08EB434";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid387" -parent "BOIDS";
	rename -uuid "649476D9-442D-5183-952B-5DACB7719326";
createNode mesh -name "boidShape387" -parent "boid387";
	rename -uuid "598A415B-4EE8-8623-3A8C-24B73C90A672";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid388" -parent "BOIDS";
	rename -uuid "2001D494-48D2-60C1-55E0-788A664C5B3C";
createNode mesh -name "boidShape388" -parent "boid388";
	rename -uuid "F83713FB-4202-212D-26B8-27BEC838CC17";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid389" -parent "BOIDS";
	rename -uuid "A1D5F4F5-4E83-F293-63CA-07B0E59AD825";
createNode mesh -name "boidShape389" -parent "boid389";
	rename -uuid "8DE46AB4-414D-12E5-985A-FC897A046E91";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid390" -parent "BOIDS";
	rename -uuid "434B3E3F-48E6-861D-DA3B-E1AB34D00B46";
createNode mesh -name "boidShape390" -parent "boid390";
	rename -uuid "0EAB45B8-4D20-8482-2FB2-24A77B156DDD";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid391" -parent "BOIDS";
	rename -uuid "8479F7B5-4534-3569-6932-B4AB6ED9C54E";
createNode mesh -name "boidShape391" -parent "boid391";
	rename -uuid "A2616BEB-4FA1-60D7-0AEB-D1B64306F984";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid392" -parent "BOIDS";
	rename -uuid "2B2460BB-40DA-6CAF-F52A-5C9C1E8027A9";
createNode mesh -name "boidShape392" -parent "boid392";
	rename -uuid "707F4726-44ED-573A-FBD5-DE9C36E92ABA";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid393" -parent "BOIDS";
	rename -uuid "715BEF76-4056-0E53-8536-0EA40B164DFD";
createNode mesh -name "boidShape393" -parent "boid393";
	rename -uuid "0961E634-4625-E883-8F1C-5093DDA1BDAE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid394" -parent "BOIDS";
	rename -uuid "44EAE3C8-47E4-FEED-F19C-1D948DDEEABE";
createNode mesh -name "boidShape394" -parent "boid394";
	rename -uuid "54D7ED64-4928-EF06-3BED-D68457FCC995";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid395" -parent "BOIDS";
	rename -uuid "0512572B-4F75-03F0-1B24-4ABEC2BD7D3C";
createNode mesh -name "boidShape395" -parent "boid395";
	rename -uuid "C0F8395B-44E2-D8B7-05B1-BF8969A093B9";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid396" -parent "BOIDS";
	rename -uuid "9DBC8A8F-4714-EC39-96B6-199ABFCACE38";
createNode mesh -name "boidShape396" -parent "boid396";
	rename -uuid "356833D9-4EFC-ECEF-40D0-179A3B273F41";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid397" -parent "BOIDS";
	rename -uuid "78BD27D6-49B8-E798-C77D-AFA3B9ADDEA7";
createNode mesh -name "boidShape397" -parent "boid397";
	rename -uuid "545F052D-4B75-6273-ECA8-5AA6D702A168";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid398" -parent "BOIDS";
	rename -uuid "6E475A89-4AFA-1DDC-593C-04A5193002D1";
createNode mesh -name "boidShape398" -parent "boid398";
	rename -uuid "3B40F847-4ECA-B50B-AEA1-5CB65095C0F7";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode transform -name "boid399" -parent "BOIDS";
	rename -uuid "7045FDD9-453B-8587-8882-1AB0EB97E521";
createNode mesh -name "boidShape399" -parent "boid399";
	rename -uuid "896493DC-4CE5-9245-1299-56A405FCF965";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
createNode lightLinker -shared -name "lightLinker1";
	rename -uuid "0A953166-4550-FA28-F32C-26BE64DFD08E";
	setAttr -size 4 ".link";
	setAttr -size 4 ".shadowLink";
createNode shapeEditorManager -name "shapeEditorManager";
	rename -uuid "25569F09-4222-07E2-48BE-F28E2F3F789D";
createNode poseInterpolatorManager -name "poseInterpolatorManager";
	rename -uuid "6AA53B60-4960-DFA5-EAF8-01A4F801C4A5";
createNode displayLayerManager -name "layerManager";
	rename -uuid "BB0F3EDD-4722-15B0-E4CF-3DAB547D451E";
createNode displayLayer -name "defaultLayer";
	rename -uuid "3DCD6829-4E63-D3C2-78AD-88B64B86178D";
createNode renderLayerManager -name "renderLayerManager";
	rename -uuid "1D508848-40FC-3F45-5DCE-BE85418D9E2B";
createNode renderLayer -name "defaultRenderLayer";
	rename -uuid "A3666D96-4901-DCC7-C932-DAA588D4387D";
	setAttr ".global" yes;
createNode polyCube -name "polyCube1";
	rename -uuid "41471B90-4F32-5C8A-D824-44B38EE364F2";
	setAttr ".createUVs" 4;
createNode script -name "sceneConfigurationScriptNode";
	rename -uuid "C3AACE9C-423F-2A09-9F2E-AFADEC3E1448";
	setAttr ".before" -type "string" "playbackOptions -min 8 -max 127 -ast 1 -aet 200 ";
	setAttr ".scriptType" 6;
createNode blinn -name "blinn1";
	rename -uuid "2B67738D-494B-DB49-9791-6F9E9E0B853A";
	setAttr ".color" -type "float3" 1 0 0 ;
createNode shadingEngine -name "blinn1SG";
	rename -uuid "3CD623F9-4FFB-51A0-EB97-6782787B1F31";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".renderableOnlySet" yes;
createNode materialInfo -name "materialInfo1";
	rename -uuid "B2F05B42-4F20-F828-B400-8AB021B0852A";
createNode blinn -name "blinn2";
	rename -uuid "69CBBD8A-42CE-6C16-EA97-40AED8385E51";
	setAttr ".color" -type "float3" 0 1 0 ;
createNode shadingEngine -name "blinn2SG";
	rename -uuid "90F681C7-4A57-17E0-D01C-3FA30088EDE0";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr -size 400 ".dagSetMembers";
	setAttr ".renderableOnlySet" yes;
createNode materialInfo -name "materialInfo2";
	rename -uuid "2F9E0179-40D8-DC3E-DB0A-12985B42E84A";
createNode mPyNode -name "mPyNode1";
	rename -uuid "9DC3E0EB-423F-4FE8-A0B3-8F8609C6F231";
	addAttr -readable false -cachedInternally true -keyable true -shortName "reset" 
		-longName "reset" -minValue 0 -maxValue 1 -enumName "False:True" -attributeType "enum";
	addAttr -readable false -cachedInternally true -shortName "time" -longName "time" 
		-attributeType "time";
	addAttr -writable false -storable false -keyable true -multi -shortName "position" 
		-longName "position" -attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -keyable true -shortName "positionX" -longName "positionX" 
		-attributeType "double" -parent "position";
	addAttr -writable false -storable false -keyable true -shortName "positionY" -longName "positionY" 
		-attributeType "double" -parent "position";
	addAttr -writable false -storable false -keyable true -shortName "positionZ" -longName "positionZ" 
		-attributeType "double" -parent "position";
	addAttr -readable false -cachedInternally true -keyable true -shortName "cohesion" 
		-longName "cohesion" -defaultValue 0.05 -minValue 0 -attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "alignment" 
		-longName "alignment" -defaultValue 1 -minValue 0 -attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "repulsion" 
		-longName "repulsion" -defaultValue 1 -minValue 0 -attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "target" 
		-longName "target" -defaultValue 0.05 -minValue 0 -attributeType "double";
	setAttr ".expression" -type "string" (
		"# Name: Boids Simulation\n# Author: Eric Vignola - eric.vignola@gmail.com\n# Adapted from: VisualPy example http://api.vispy.org/en/v0.2.1/examples/demo/boids.html\n# \n# Demonstrates: - Usage of numpy and scipy inside MPyNode\n#\n# Explanation: Boids is an artificial life program, developed by Craig Reynolds in 1986,\n#              which simulates the flocking behaviour of birds.\n#\n# Dependencies: Numpy and Scipy compiled for Maya, available below\n#               Numpy: https://bitbucket.org/eric-vignola/numpy/src/master/\n#               Scipy: https://bitbucket.org/eric-vignola/scipy/src/master/\n\nimport numpy as np\nfrom scipy.spatial import cKDTree\n\n\nboidCount = len(position)\nalignment = alignment/100.\ncohesion  = cohesion/100.\nrepulsion = repulsion/100.\ntarget    = target/100.\n\nif not hasattr(self,'position') or reset:\n    self.velocity = (1.-np.random.random((boidCount,3))*2)\n    self.position = (1.-np.random.random((boidCount,3))*2) * 20\n    self.time = 0.\n    self.target = None\n\n\n# Pick a random leader every x frames\n"
		+ "self.time = self.time % 300\nif self.time == 0.:\n    self.target = np.random.choice(boidCount)\n    self.target = np.array(self.position[self.target])\n\n\n# Cohesion: steer to move toward the average position of local flockmates\nC = -(self.position - self.position.sum(axis=0)/boidCount) * cohesion\n\n# Alignment: steer towards the average heading of local flockmates\nA = -(self.velocity - self.velocity.sum(axis=0)/boidCount) * alignment\n\n# Repulsion: steer to avoid crowding local flockmates\nD,I = cKDTree(self.position).query(self.position,5)\nM = np.repeat(D < 5, 3, axis=1).reshape(boidCount,5,3)\nZ = np.repeat(self.position,5,axis=0).reshape(boidCount,5,3)\nR = -((self.position[I]-Z)*M).sum(axis=1) * repulsion\n\n# Target : Follow target\nT = (self.target - self.position) * target\n\n\nself.velocity+= C + A + R + T\nself.position += self.velocity\n\nposition = self.position \n\n\nself.time += 1");
	setAttr "._inputAttrs" -type "string" "gAJ9cQEoVQVyZXNldF1xAlUEZW51bXEDYVgGAAAAdGFyZ2V0cQRdcQVYBQAAAGZsb2F0cQZhWAgA\nAABjb2hlc2lvbl1xB1gFAAAAZmxvYXRxCGFYCQAAAHJlcHVsc2lvbl1xCVgFAAAAZmxvYXRxCmFY\nBAAAAHRpbWVdcQtYBAAAAHRpbWVxDGFYCQAAAGFsaWdubWVudF1xDVgFAAAAZmxvYXRxDmF1Lg==\n";
	setAttr "._outputAttrs" -type "string" "gAJ9cQFVCHBvc2l0aW9uXXECVQZ2ZWN0b3JxA2FzLg==\n";
	setAttr "._storedVarNames" -type "string" "gAJOLg==\n";
	setAttr "._storedVarsData" -type "string" "gAJ9cQEu\n";
	setAttr -size 400 ".position";
	setAttr -keyable on ".alignment" 0.1;
	setAttr -keyable on ".repulsion" 0.1;
createNode nodeGraphEditorInfo -name "hyperShadePrimaryNodeEditorSavedTabsInfo";
	rename -uuid "C82A23DB-4B55-8944-A198-1A9E70A7CE0F";
	setAttr ".tabGraphInfo[0].tabName" -type "string" "Untitled_1";
	setAttr ".tabGraphInfo[0].viewRectLow" -type "double2" -389.88093688847596 -324.40474901407538 ;
	setAttr ".tabGraphInfo[0].viewRectHigh" -type "double2" 139.88094682258301 337.49998658895549 ;
	setAttr -size 4 ".tabGraphInfo[0].nodeInfo";
	setAttr ".tabGraphInfo[0].nodeInfo[0].positionX" -312.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[0].positionY" 194.28572082519531;
	setAttr ".tabGraphInfo[0].nodeInfo[0].nodeVisualState" 1923;
	setAttr ".tabGraphInfo[0].nodeInfo[1].positionX" -5.7142858505249023;
	setAttr ".tabGraphInfo[0].nodeInfo[1].positionY" 190;
	setAttr ".tabGraphInfo[0].nodeInfo[1].nodeVisualState" 1923;
	setAttr ".tabGraphInfo[0].nodeInfo[2].positionX" -5.7142858505249023;
	setAttr ".tabGraphInfo[0].nodeInfo[2].positionY" 194.28572082519531;
	setAttr ".tabGraphInfo[0].nodeInfo[2].nodeVisualState" 1923;
	setAttr ".tabGraphInfo[0].nodeInfo[3].positionX" -312.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[3].positionY" 190;
	setAttr ".tabGraphInfo[0].nodeInfo[3].nodeVisualState" 1923;
createNode nodeGraphEditorInfo -name "MayaNodeEditorSavedTabsInfo";
	rename -uuid "410D77FB-44C9-A834-3949-F98E78DDD88E";
	setAttr ".parentEditorEmbedded" yes;
	setAttr ".tabGraphInfo[0].tabName" -type "string" "Untitled_1";
	setAttr ".tabGraphInfo[0].viewRectLow" -type "double2" -24036.583293956242 -12352.700974349227 ;
	setAttr ".tabGraphInfo[0].viewRectHigh" -type "double2" 30714.559219073511 12457.508662492237 ;
	setAttr -size 810 ".tabGraphInfo[0].nodeInfo";
	setAttr ".tabGraphInfo[0].nodeInfo[0].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[0].positionY" -2112.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[0].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[1].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[1].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[1].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[2].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[2].positionY" 10367.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[2].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[3].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[3].positionY" -8872.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[3].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[4].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[4].positionY" -1592.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[4].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[5].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[5].positionY" -10952.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[5].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[6].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[6].positionY" 2567.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[6].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[7].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[7].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[7].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[8].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[8].positionY" -4712.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[8].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[9].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[9].positionY" -3932.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[9].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[10].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[10].positionY" 4907.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[10].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[11].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[11].positionY" -6012.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[11].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[12].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[12].positionY" 8807.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[12].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[13].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[13].positionY" -2112.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[13].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[14].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[14].positionY" 8807.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[14].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[15].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[15].positionY" 10107.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[15].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[16].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[16].positionY" -3022.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[16].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[17].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[17].positionY" -8092.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[17].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[18].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[18].positionY" 4387.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[18].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[19].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[19].positionY" -3412.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[19].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[20].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[20].positionY" 11407.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[20].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[21].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[21].positionY" -10692.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[21].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[22].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[22].positionY" 3477.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[22].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[23].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[23].positionY" 8547.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[23].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[24].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[24].positionY" -9392.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[24].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[25].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[25].positionY" -9002.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[25].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[26].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[26].positionY" 6857.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[26].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[27].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[27].positionY" 6727.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[27].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[28].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[28].positionY" -6792.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[28].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[29].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[29].positionY" 11017.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[29].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[30].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[30].positionY" 12707.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[30].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[31].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[31].positionY" 3347.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[31].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[32].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[32].positionY" 10237.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[32].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[33].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[33].positionY" -7572.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[33].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[34].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[34].positionY" 9717.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[34].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[35].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[35].positionY" 747.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[35].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[36].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[36].positionY" 1137.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[36].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[37].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[37].positionY" 12187.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[37].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[38].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[38].positionY" -1202.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[38].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[39].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[39].positionY" 2957.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[39].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[40].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[40].positionY" -1722.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[40].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[41].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[41].positionY" -5882.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[41].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[42].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[42].positionY" 8287.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[42].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[43].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[43].positionY" 5817.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[43].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[44].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[44].positionY" -812.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[44].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[45].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[45].positionY" -10172.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[45].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[46].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[46].positionY" 10367.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[46].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[47].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[47].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[47].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[48].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[48].positionY" 1657.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[48].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[49].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[49].positionY" 2047.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[49].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[50].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[50].positionY" -3412.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[50].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[51].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[51].positionY" -162.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[51].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[52].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[52].positionY" 5427.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[52].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[53].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[53].positionY" -2242.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[53].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[54].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[54].positionY" 5557.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[54].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[55].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[55].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[55].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[56].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[56].positionY" -6662.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[56].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[57].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[57].positionY" -6922.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[57].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[58].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[58].positionY" -162.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[58].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[59].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[59].positionY" -812.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[59].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[60].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[60].positionY" 6337.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[60].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[61].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[61].positionY" 4647.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[61].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[62].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[62].positionY" 8157.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[62].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[63].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[63].positionY" 1527.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[63].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[64].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[64].positionY" 11537.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[64].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[65].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[65].positionY" -682.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[65].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[66].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[66].positionY" 6467.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[66].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[67].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[67].positionY" 10757.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[67].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[68].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[68].positionY" 4777.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[68].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[69].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[69].positionY" 2697.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[69].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[70].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[70].positionY" 12057.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[70].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[71].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[71].positionY" -2242.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[71].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[72].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[72].positionY" 487.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[72].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[73].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[73].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[73].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[74].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[74].positionY" 357.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[74].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[75].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[75].positionY" 617.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[75].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[76].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[76].positionY" -9782.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[76].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[77].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[77].positionY" -552.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[77].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[78].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[78].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[78].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[79].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[79].positionY" 8677.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[79].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[80].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[80].positionY" 9067.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[80].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[81].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[81].positionY" 3737.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[81].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[82].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[82].positionY" 227.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[82].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[83].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[83].positionY" -4842.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[83].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[84].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[84].positionY" 3087.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[84].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[85].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[85].positionY" -1202.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[85].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[86].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[86].positionY" -3022.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[86].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[87].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[87].positionY" 2437.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[87].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[88].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[88].positionY" 12577.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[88].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[89].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[89].positionY" -9262.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[89].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[90].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[90].positionY" -9262.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[90].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[91].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[91].positionY" 2307.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[91].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[92].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[92].positionY" 227.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[92].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[93].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[93].positionY" -7442.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[93].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[94].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[94].positionY" 877.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[94].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[95].positionX" 265.71429443359375;
	setAttr ".tabGraphInfo[0].nodeInfo[95].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[95].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[96].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[96].positionY" -422.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[96].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[97].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[97].positionY" 3997.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[97].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[98].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[98].positionY" 747.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[98].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[99].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[99].positionY" -1722.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[99].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[100].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[100].positionY" -1462.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[100].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[101].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[101].positionY" 11017.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[101].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[102].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[102].positionY" -1462.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[102].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[103].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[103].positionY" -1072.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[103].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[104].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[104].positionY" 7507.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[104].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[105].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[105].positionY" -2502.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[105].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[106].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[106].positionY" 3607.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[106].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[107].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[107].positionY" 10887.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[107].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[108].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[108].positionY" -9912.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[108].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[109].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[109].positionY" -11602.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[109].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[110].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[110].positionY" 9587.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[110].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[111].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[111].positionY" -4972.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[111].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[112].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[112].positionY" 2437.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[112].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[113].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[113].positionY" -8352.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[113].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[114].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[114].positionY" 227.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[114].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[115].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[115].positionY" -10302.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[115].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[116].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[116].positionY" -5492.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[116].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[117].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[117].positionY" 8937.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[117].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[118].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[118].positionY" 11147.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[118].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[119].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[119].positionY" -10692.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[119].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[120].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[120].positionY" 2177.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[120].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[121].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[121].positionY" -8742.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[121].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[122].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[122].positionY" -8612.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[122].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[123].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[123].positionY" 877.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[123].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[124].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[124].positionY" -12252.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[124].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[125].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[125].positionY" 8677.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[125].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[126].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[126].positionY" -4062.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[126].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[127].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[127].positionY" -3802.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[127].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[128].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[128].positionY" 10887.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[128].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[129].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[129].positionY" 12837.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[129].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[130].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[130].positionY" 8807.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[130].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[131].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[131].positionY" -10432.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[131].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[132].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[132].positionY" 6337.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[132].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[133].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[133].positionY" -11342.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[133].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[134].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[134].positionY" 1527.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[134].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[135].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[135].positionY" -5102.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[135].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[136].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[136].positionY" -4842.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[136].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[137].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[137].positionY" -10562.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[137].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[138].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[138].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[138].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[139].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[139].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[139].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[140].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[140].positionY" 9067.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[140].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[141].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[141].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[141].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[142].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[142].positionY" -552.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[142].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[143].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[143].positionY" 5817.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[143].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[144].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[144].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[144].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[145].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[145].positionY" 8937.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[145].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[146].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[146].positionY" 1527.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[146].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[147].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[147].positionY" 12317.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[147].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[148].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[148].positionY" 6597.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[148].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[149].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[149].positionY" -1462.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[149].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[150].positionX" 61.428569793701172;
	setAttr ".tabGraphInfo[0].nodeInfo[150].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[150].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[151].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[151].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[151].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[152].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[152].positionY" 5037.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[152].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[153].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[153].positionY" -2112.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[153].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[154].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[154].positionY" 9457.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[154].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[155].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[155].positionY" 6467.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[155].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[156].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[156].positionY" -5622.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[156].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[157].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[157].positionY" 12837.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[157].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[158].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[158].positionY" -9392.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[158].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[159].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[159].positionY" 9587.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[159].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[160].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[160].positionY" 2177.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[160].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[161].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[161].positionY" -7182.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[161].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[162].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[162].positionY" 5167.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[162].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[163].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[163].positionY" 11277.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[163].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[164].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[164].positionY" -12252.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[164].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[165].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[165].positionY" 5167.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[165].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[166].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[166].positionY" -9522.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[166].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[167].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[167].positionY" 1007.1428833007813;
	setAttr ".tabGraphInfo[0].nodeInfo[167].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[168].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[168].positionY" -6922.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[168].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[169].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[169].positionY" 11797.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[169].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[170].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[170].positionY" -5882.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[170].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[171].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[171].positionY" 12577.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[171].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[172].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[172].positionY" 4257.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[172].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[173].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[173].positionY" 6987.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[173].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[174].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[174].positionY" -552.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[174].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[175].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[175].positionY" -12382.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[175].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[176].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[176].positionY" 3997.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[176].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[177].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[177].positionY" -1072.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[177].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[178].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[178].positionY" -4192.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[178].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[179].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[179].positionY" -2372.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[179].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[180].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[180].positionY" 11667.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[180].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[181].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[181].positionY" 10497.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[181].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[182].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[182].positionY" -2242.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[182].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[183].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[183].positionY" -1462.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[183].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[184].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[184].positionY" 4257.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[184].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[185].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[185].positionY" -12642.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[185].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[186].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[186].positionY" -1332.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[186].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[187].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[187].positionY" -9522.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[187].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[188].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[188].positionY" 2307.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[188].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[189].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[189].positionY" -682.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[189].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[190].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[190].positionY" -10172.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[190].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[191].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[191].positionY" -3282.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[191].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[192].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[192].positionY" -1202.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[192].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[193].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[193].positionY" -8612.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[193].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[194].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[194].positionY" -4972.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[194].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[195].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[195].positionY" -1332.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[195].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[196].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[196].positionY" 8937.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[196].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[197].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[197].positionY" 1137.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[197].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[198].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[198].positionY" -11082.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[198].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[199].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[199].positionY" -6012.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[199].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[200].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[200].positionY" -4452.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[200].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[201].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[201].positionY" -11212.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[201].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[202].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[202].positionY" 7377.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[202].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[203].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[203].positionY" -12512.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[203].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[204].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[204].positionY" -1072.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[204].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[205].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[205].positionY" -812.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[205].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[206].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[206].positionY" 1397.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[206].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[207].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[207].positionY" 6857.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[207].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[208].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[208].positionY" 2437.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[208].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[209].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[209].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[209].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[210].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[210].positionY" 10887.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[210].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[211].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[211].positionY" 6597.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[211].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[212].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[212].positionY" -1202.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[212].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[213].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[213].positionY" 1397.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[213].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[214].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[214].positionY" 2567.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[214].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[215].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[215].positionY" 3217.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[215].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[216].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[216].positionY" 1137.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[216].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[217].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[217].positionY" 12707.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[217].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[218].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[218].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[218].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[219].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[219].positionY" 3867.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[219].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[220].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[220].positionY" 9197.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[220].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[221].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[221].positionY" -12382.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[221].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[222].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[222].positionY" -7182.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[222].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[223].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[223].positionY" -12512.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[223].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[224].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[224].positionY" -1592.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[224].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[225].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[225].positionY" -11602.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[225].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[226].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[226].positionY" 3217.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[226].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[227].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[227].positionY" 4777.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[227].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[228].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[228].positionY" 2177.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[228].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[229].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[229].positionY" 1007.1428833007813;
	setAttr ".tabGraphInfo[0].nodeInfo[229].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[230].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[230].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[230].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[231].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[231].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[231].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[232].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[232].positionY" 2827.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[232].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[233].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[233].positionY" 1657.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[233].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[234].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[234].positionY" 5557.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[234].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[235].positionX" -1078.5714111328125;
	setAttr ".tabGraphInfo[0].nodeInfo[235].positionY" -225.71427917480469;
	setAttr ".tabGraphInfo[0].nodeInfo[235].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[236].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[236].positionY" -1202.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[236].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[237].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[237].positionY" -4192.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[237].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[238].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[238].positionY" -2242.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[238].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[239].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[239].positionY" 487.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[239].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[240].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[240].positionY" -4322.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[240].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[241].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[241].positionY" -11862.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[241].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[242].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[242].positionY" -2502.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[242].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[243].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[243].positionY" 5817.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[243].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[244].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[244].positionY" -6662.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[244].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[245].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[245].positionY" 3737.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[245].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[246].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[246].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[246].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[247].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[247].positionY" -8612.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[247].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[248].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[248].positionY" 5687.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[248].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[249].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[249].positionY" 9197.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[249].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[250].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[250].positionY" -8352.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[250].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[251].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[251].positionY" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[251].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[252].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[252].positionY" 11797.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[252].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[253].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[253].positionY" 7247.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[253].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[254].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[254].positionY" -1722.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[254].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[255].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[255].positionY" 10627.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[255].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[256].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[256].positionY" -11992.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[256].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[257].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[257].positionY" 1137.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[257].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[258].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[258].positionY" -5362.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[258].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[259].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[259].positionY" -1592.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[259].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[260].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[260].positionY" 1787.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[260].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[261].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[261].positionY" 2307.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[261].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[262].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[262].positionY" 227.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[262].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[263].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[263].positionY" -292.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[263].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[264].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[264].positionY" -4322.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[264].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[265].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[265].positionY" 9327.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[265].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[266].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[266].positionY" 2047.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[266].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[267].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[267].positionY" -5752.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[267].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[268].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[268].positionY" -10302.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[268].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[269].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[269].positionY" -12772.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[269].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[270].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[270].positionY" 11667.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[270].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[271].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[271].positionY" -3152.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[271].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[272].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[272].positionY" -9652.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[272].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[273].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[273].positionY" 10757.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[273].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[274].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[274].positionY" 1787.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[274].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[275].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[275].positionY" -6922.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[275].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[276].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[276].positionY" 357.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[276].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[277].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[277].positionY" 12577.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[277].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[278].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[278].positionY" -1332.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[278].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[279].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[279].positionY" 2957.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[279].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[280].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[280].positionY" 8157.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[280].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[281].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[281].positionY" 1527.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[281].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[282].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[282].positionY" -2112.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[282].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[283].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[283].positionY" 1137.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[283].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[284].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[284].positionY" 11537.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[284].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[285].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[285].positionY" 1007.1428833007813;
	setAttr ".tabGraphInfo[0].nodeInfo[285].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[286].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[286].positionY" -8222.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[286].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[287].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[287].positionY" 8547.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[287].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[288].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[288].positionY" -2372.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[288].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[289].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[289].positionY" 12187.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[289].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[290].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[290].positionY" 1917.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[290].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[291].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[291].positionY" -10562.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[291].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[292].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[292].positionY" -5622.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[292].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[293].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[293].positionY" -1072.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[293].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[294].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[294].positionY" 2437.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[294].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[295].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[295].positionY" -10432.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[295].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[296].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[296].positionY" 5557.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[296].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[297].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[297].positionY" -9782.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[297].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[298].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[298].positionY" -9132.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[298].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[299].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[299].positionY" 9067.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[299].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[300].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[300].positionY" 7897.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[300].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[301].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[301].positionY" 9847.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[301].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[302].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[302].positionY" 747.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[302].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[303].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[303].positionY" -11472.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[303].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[304].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[304].positionY" -7572.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[304].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[305].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[305].positionY" 7377.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[305].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[306].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[306].positionY" 1657.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[306].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[307].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[307].positionY" -5882.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[307].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[308].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[308].positionY" 2827.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[308].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[309].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[309].positionY" -5102.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[309].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[310].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[310].positionY" 357.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[310].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[311].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[311].positionY" -12642.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[311].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[312].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[312].positionY" -9782.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[312].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[313].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[313].positionY" -682.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[313].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[314].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[314].positionY" -8482.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[314].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[315].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[315].positionY" -942.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[315].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[316].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[316].positionY" 7247.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[316].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[317].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[317].positionY" 9717.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[317].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[318].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[318].positionY" 1917.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[318].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[319].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[319].positionY" -12122.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[319].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[320].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[320].positionY" -8742.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[320].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[321].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[321].positionY" 11927.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[321].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[322].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[322].positionY" -2242.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[322].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[323].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[323].positionY" -1462.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[323].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[324].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[324].positionY" 4647.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[324].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[325].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[325].positionY" -422.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[325].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[326].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[326].positionY" 7377.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[326].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[327].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[327].positionY" -2632.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[327].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[328].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[328].positionY" -1332.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[328].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[329].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[329].positionY" 9717.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[329].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[330].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[330].positionY" -3542.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[330].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[331].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[331].positionY" -3022.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[331].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[332].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[332].positionY" 12317.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[332].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[333].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[333].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[333].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[334].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[334].positionY" 1137.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[334].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[335].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[335].positionY" -682.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[335].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[336].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[336].positionY" 4907.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[336].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[337].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[337].positionY" -4712.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[337].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[338].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[338].positionY" 4387.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[338].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[339].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[339].positionY" 3477.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[339].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[340].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[340].positionY" -292.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[340].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[341].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[341].positionY" -5752.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[341].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[342].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[342].positionY" 1007.1428833007813;
	setAttr ".tabGraphInfo[0].nodeInfo[342].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[343].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[343].positionY" -812.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[343].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[344].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[344].positionY" -4972.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[344].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[345].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[345].positionY" -12252.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[345].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[346].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[346].positionY" 6077.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[346].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[347].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[347].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[347].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[348].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[348].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[348].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[349].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[349].positionY" -1982.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[349].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[350].positionX" 212.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[350].positionY" 137.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[350].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[351].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[351].positionY" -1592.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[351].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[352].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[352].positionY" -292.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[352].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[353].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[353].positionY" -6142.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[353].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[354].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[354].positionY" -1852.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[354].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[355].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[355].positionY" -6142.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[355].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[356].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[356].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[356].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[357].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[357].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[357].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[358].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[358].positionY" 2957.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[358].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[359].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[359].positionY" -162.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[359].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[360].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[360].positionY" -7182.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[360].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[361].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[361].positionY" -9132.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[361].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[362].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[362].positionY" 4517.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[362].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[363].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[363].positionY" 12967.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[363].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[364].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[364].positionY" -1722.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[364].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[365].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[365].positionY" 12317.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[365].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[366].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[366].positionY" -1072.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[366].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[367].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[367].positionY" 747.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[367].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[368].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[368].positionY" 9587.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[368].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[369].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[369].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[369].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[370].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[370].positionY" -9392.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[370].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[371].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[371].positionY" -2502.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[371].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[372].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[372].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[372].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[373].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[373].positionY" -10562.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[373].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[374].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[374].positionY" 1007.1428833007813;
	setAttr ".tabGraphInfo[0].nodeInfo[374].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[375].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[375].positionY" 2047.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[375].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[376].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[376].positionY" 10627.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[376].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[377].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[377].positionY" 1787.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[377].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[378].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[378].positionY" -942.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[378].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[379].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[379].positionY" 6337.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[379].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[380].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[380].positionY" 11537.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[380].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[381].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[381].positionY" -10042.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[381].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[382].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[382].positionY" 1917.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[382].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[383].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[383].positionY" -4582.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[383].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[384].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[384].positionY" 12447.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[384].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[385].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[385].positionY" -9522.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[385].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[386].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[386].positionY" -2372.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[386].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[387].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[387].positionY" 5037.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[387].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[388].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[388].positionY" 9977.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[388].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[389].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[389].positionY" 11927.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[389].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[390].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[390].positionY" -1852.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[390].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[391].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[391].positionY" -2892.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[391].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[392].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[392].positionY" -6662.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[392].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[393].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[393].positionY" -162.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[393].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[394].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[394].positionY" -8872.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[394].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[395].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[395].positionY" -812.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[395].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[396].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[396].positionY" -11862.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[396].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[397].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[397].positionY" -5232.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[397].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[398].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[398].positionY" -7052.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[398].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[399].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[399].positionY" -10042.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[399].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[400].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[400].positionY" -12512.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[400].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[401].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[401].positionY" 617.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[401].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[402].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[402].positionY" 617.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[402].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[403].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[403].positionY" 12447.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[403].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[404].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[404].positionY" -7962.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[404].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[405].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[405].positionY" -1332.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[405].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[406].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[406].positionY" -1852.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[406].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[407].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[407].positionY" 3217.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[407].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[408].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[408].positionY" 8417.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[408].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[409].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[409].positionY" -7832.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[409].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[410].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[410].positionY" 5687.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[410].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[411].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[411].positionY" 487.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[411].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[412].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[412].positionY" -4452.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[412].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[413].positionX" -450;
	setAttr ".tabGraphInfo[0].nodeInfo[413].positionY" 31.428571701049805;
	setAttr ".tabGraphInfo[0].nodeInfo[413].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[414].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[414].positionY" 7897.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[414].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[415].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[415].positionY" -4582.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[415].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[416].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[416].positionY" -12122.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[416].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[417].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[417].positionY" -5362.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[417].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[418].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[418].positionY" 2437.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[418].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[419].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[419].positionY" 2177.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[419].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[420].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[420].positionY" -9912.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[420].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[421].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[421].positionY" 11017.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[421].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[422].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[422].positionY" -3672.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[422].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[423].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[423].positionY" -6272.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[423].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[424].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[424].positionY" 747.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[424].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[425].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[425].positionY" -3282.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[425].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[426].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[426].positionY" -11212.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[426].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[427].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[427].positionY" -10822.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[427].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[428].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[428].positionY" -1852.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[428].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[429].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[429].positionY" 1527.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[429].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[430].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[430].positionY" -2502.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[430].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[431].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[431].positionY" 1657.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[431].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[432].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[432].positionY" -552.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[432].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[433].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[433].positionY" -682.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[433].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[434].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[434].positionY" 487.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[434].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[435].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[435].positionY" 3087.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[435].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[436].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[436].positionY" -12122.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[436].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[437].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[437].positionY" 3347.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[437].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[438].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[438].positionY" 8287.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[438].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[439].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[439].positionY" -2372.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[439].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[440].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[440].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[440].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[441].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[441].positionY" 2047.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[441].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[442].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[442].positionY" 2567.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[442].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[443].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[443].positionY" 4907.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[443].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[444].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[444].positionY" 617.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[444].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[445].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[445].positionY" 4127.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[445].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[446].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[446].positionY" -5492.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[446].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[447].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[447].positionY" 4387.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[447].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[448].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[448].positionY" 2567.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[448].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[449].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[449].positionY" 1657.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[449].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[450].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[450].positionY" 8027.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[450].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[451].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[451].positionY" -8482.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[451].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[452].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[452].positionY" -5102.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[452].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[453].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[453].positionY" -12642.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[453].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[454].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[454].positionY" -4452.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[454].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[455].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[455].positionY" 5947.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[455].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[456].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[456].positionY" 1397.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[456].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[457].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[457].positionY" -6532.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[457].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[458].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[458].positionY" -6402.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[458].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[459].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[459].positionY" 7117.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[459].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[460].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[460].positionY" 7767.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[460].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[461].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[461].positionY" -3412.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[461].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[462].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[462].positionY" -812.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[462].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[463].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[463].positionY" 1267.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[463].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[464].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[464].positionY" 12057.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[464].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[465].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[465].positionY" -10432.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[465].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[466].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[466].positionY" -4712.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[466].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[467].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[467].positionY" -8092.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[467].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[468].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[468].positionY" 12707.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[468].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[469].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[469].positionY" 7117.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[469].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[470].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[470].positionY" -2112.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[470].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[471].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[471].positionY" 227.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[471].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[472].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[472].positionY" 11407.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[472].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[473].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[473].positionY" -6142.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[473].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[474].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[474].positionY" -552.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[474].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[475].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[475].positionY" 11407.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[475].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[476].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[476].positionY" 617.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[476].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[477].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[477].positionY" 1397.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[477].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[478].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[478].positionY" 4127.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[478].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[479].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[479].positionY" 6077.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[479].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[480].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[480].positionY" -942.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[480].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[481].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[481].positionY" 4127.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[481].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[482].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[482].positionY" 5947.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[482].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[483].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[483].positionY" -2632.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[483].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[484].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[484].positionY" -422.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[484].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[485].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[485].positionY" -5232.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[485].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[486].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[486].positionY" -9002.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[486].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[487].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[487].positionY" -3802.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[487].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[488].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[488].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[488].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[489].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[489].positionY" -9262.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[489].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[490].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[490].positionY" 877.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[490].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[491].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[491].positionY" 11797.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[491].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[492].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[492].positionY" 877.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[492].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[493].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[493].positionY" 2177.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[493].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[494].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[494].positionY" 487.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[494].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[495].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[495].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[495].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[496].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[496].positionY" 11277.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[496].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[497].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[497].positionY" 9457.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[497].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[498].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[498].positionY" 1787.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[498].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[499].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[499].positionY" -12772.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[499].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[500].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[500].positionY" 9197.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[500].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[501].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[501].positionY" 3477.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[501].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[502].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[502].positionY" -11992.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[502].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[503].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[503].positionY" -7052.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[503].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[504].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[504].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[504].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[505].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[505].positionY" -8872.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[505].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[506].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[506].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[506].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[507].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[507].positionY" 357.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[507].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[508].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[508].positionY" -6532.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[508].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[509].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[509].positionY" -11732.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[509].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[510].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[510].positionY" -1722.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[510].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[511].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[511].positionY" 10627.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[511].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[512].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[512].positionY" 3737.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[512].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[513].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[513].positionY" -6402.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[513].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[514].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[514].positionY" 12967.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[514].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[515].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[515].positionY" -7702.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[515].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[516].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[516].positionY" -1332.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[516].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[517].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[517].positionY" -2502.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[517].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[518].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[518].positionY" -162.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[518].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[519].positionX" -245.71427917480469;
	setAttr ".tabGraphInfo[0].nodeInfo[519].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[519].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[520].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[520].positionY" 5297.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[520].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[521].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[521].positionY" -5492.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[521].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[522].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[522].positionY" -12902.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[522].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[523].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[523].positionY" -11992.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[523].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[524].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[524].positionY" 10497.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[524].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[525].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[525].positionY" -2372.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[525].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[526].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[526].positionY" 5687.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[526].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[527].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[527].positionY" -1592.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[527].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[528].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[528].positionY" 3607.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[528].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[529].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[529].positionY" -3152.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[529].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[530].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[530].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[530].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[531].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[531].positionY" 7507.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[531].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[532].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[532].positionY" 5427.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[532].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[533].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[533].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[533].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[534].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[534].positionY" -10692.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[534].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[535].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[535].positionY" 5427.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[535].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[536].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[536].positionY" -4322.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[536].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[537].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[537].positionY" 155.71427917480469;
	setAttr ".tabGraphInfo[0].nodeInfo[537].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[538].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[538].positionY" -10822.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[538].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[539].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[539].positionY" -422.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[539].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[540].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[540].positionY" -2762.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[540].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[541].positionX" 61.428569793701172;
	setAttr ".tabGraphInfo[0].nodeInfo[541].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[541].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[542].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[542].positionY" 6987.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[542].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[543].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[543].positionY" -7312.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[543].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[544].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[544].positionY" -9912.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[544].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[545].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[545].positionY" 1267.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[545].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[546].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[546].positionY" 7637.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[546].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[547].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[547].positionY" -5622.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[547].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[548].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[548].positionY" -6792.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[548].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[549].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[549].positionY" 12187.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[549].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[550].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[550].positionY" 2697.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[550].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[551].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[551].positionY" -292.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[551].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[552].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[552].positionY" -2372.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[552].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[553].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[553].positionY" 1397.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[553].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[554].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[554].positionY" -1982.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[554].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[555].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[555].positionY" -1722.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[555].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[556].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[556].positionY" -10952.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[556].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[557].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[557].positionY" 1267.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[557].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[558].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[558].positionY" 6207.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[558].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[559].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[559].positionY" 5037.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[559].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[560].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[560].positionY" 1527.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[560].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[561].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[561].positionY" -5752.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[561].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[562].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[562].positionY" -7312.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[562].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[563].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[563].positionY" 1917.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[563].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[564].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[564].positionY" 747.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[564].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[565].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[565].positionY" -7442.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[565].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[566].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[566].positionY" 1787.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[566].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[567].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[567].positionY" 2307.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[567].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[568].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[568].positionY" -1982.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[568].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[569].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[569].positionY" -8352.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[569].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[570].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[570].positionY" 877.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[570].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[571].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[571].positionY" 2307.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[571].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[572].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[572].positionY" 227.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[572].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[573].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[573].positionY" -2502.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[573].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[574].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[574].positionY" 1267.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[574].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[575].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[575].positionY" -11732.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[575].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[576].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[576].positionY" 6727.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[576].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[577].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[577].positionY" -4192.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[577].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[578].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[578].positionY" -6012.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[578].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[579].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[579].positionY" -1852.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[579].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[580].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[580].positionY" 6857.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[580].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[581].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[581].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[581].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[582].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[582].positionY" 1657.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[582].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[583].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[583].positionY" 5297.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[583].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[584].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[584].positionY" -292.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[584].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[585].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[585].positionY" -942.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[585].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[586].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[586].positionY" -8222.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[586].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[587].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[587].positionY" -1072.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[587].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[588].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[588].positionY" -1852.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[588].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[589].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[589].positionY" -11342.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[589].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[590].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[590].positionY" -11472.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[590].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[591].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[591].positionY" 2047.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[591].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[592].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[592].positionY" 1397.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[592].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[593].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[593].positionY" -2242.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[593].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[594].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[594].positionY" 8027.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[594].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[595].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[595].positionY" 1137.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[595].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[596].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[596].positionY" 877.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[596].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[597].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[597].positionY" 8677.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[597].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[598].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[598].positionY" -11732.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[598].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[599].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[599].positionY" -11082.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[599].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[600].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[600].positionY" -11342.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[600].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[601].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[601].positionY" -3282.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[601].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[602].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[602].positionY" 1397.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[602].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[603].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[603].positionY" -10042.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[603].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[604].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[604].positionY" 7767.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[604].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[605].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[605].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[605].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[606].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[606].positionY" 9457.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[606].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[607].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[607].positionY" 7117.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[607].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[608].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[608].positionY" -942.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[608].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[609].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[609].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[609].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[610].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[610].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[610].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[611].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[611].positionY" 617.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[611].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[612].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[612].positionY" -6402.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[612].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[613].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[613].positionY" 2177.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[613].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[614].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[614].positionY" -1982.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[614].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[615].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[615].positionY" -1852.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[615].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[616].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[616].positionY" -422.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[616].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[617].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[617].positionY" 2567.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[617].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[618].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[618].positionY" -3672.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[618].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[619].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[619].positionY" 2697.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[619].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[620].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[620].positionY" 6727.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[620].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[621].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[621].positionY" 5167.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[621].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[622].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[622].positionY" 7637.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[622].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[623].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[623].positionY" -162.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[623].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[624].positionX" -771.4285888671875;
	setAttr ".tabGraphInfo[0].nodeInfo[624].positionY" -377.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[624].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[625].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[625].positionY" 10107.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[625].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[626].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[626].positionY" -162.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[626].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[627].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[627].positionY" 4647.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[627].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[628].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[628].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[628].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[629].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[629].positionY" 1267.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[629].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[630].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[630].positionY" 4257.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[630].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[631].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[631].positionY" -6532.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[631].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[632].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[632].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[632].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[633].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[633].positionY" -2632.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[633].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[634].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[634].positionY" 7637.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[634].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[635].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[635].positionY" 6077.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[635].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[636].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[636].positionY" 8547.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[636].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[637].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[637].positionY" -12902.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[637].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[638].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[638].positionY" -9652.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[638].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[639].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[639].positionY" -8222.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[639].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[640].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[640].positionY" -942.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[640].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[641].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[641].positionY" 1007.1428833007813;
	setAttr ".tabGraphInfo[0].nodeInfo[641].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[642].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[642].positionY" 2047.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[642].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[643].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[643].positionY" -4842.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[643].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[644].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[644].positionY" -12382.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[644].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[645].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[645].positionY" 10107.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[645].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[646].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[646].positionY" 10237.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[646].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[647].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[647].positionY" -812.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[647].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[648].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[648].positionY" 1917.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[648].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[649].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[649].positionY" -422.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[649].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[650].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[650].positionY" -3542.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[650].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[651].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[651].positionY" 11277.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[651].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[652].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[652].positionY" 2307.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[652].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[653].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[653].positionY" -11212.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[653].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[654].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[654].positionY" -1592.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[654].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[655].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[655].positionY" -292.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[655].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[656].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[656].positionY" 8287.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[656].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[657].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[657].positionY" 11147.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[657].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[658].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[658].positionY" 3997.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[658].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[659].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[659].positionY" -8482.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[659].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[660].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[660].positionY" -1202.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[660].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[661].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[661].positionY" -1462.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[661].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[662].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[662].positionY" 2437.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[662].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[663].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[663].positionY" 9977.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[663].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[664].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[664].positionY" 487.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[664].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[665].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[665].positionY" -682.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[665].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[666].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[666].positionY" 1267.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[666].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[667].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[667].positionY" 6207.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[667].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[668].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[668].positionY" 10237.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[668].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[669].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[669].positionY" 2567.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[669].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[670].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[670].positionY" 877.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[670].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[671].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[671].positionY" 2827.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[671].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[672].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[672].positionY" 9977.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[672].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[673].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[673].positionY" 2437.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[673].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[674].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[674].positionY" 8027.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[674].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[675].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[675].positionY" 9327.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[675].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[676].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[676].positionY" -1332.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[676].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[677].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[677].positionY" -1982.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[677].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[678].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[678].positionY" -3152.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[678].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[679].positionX" 375.71429443359375;
	setAttr ".tabGraphInfo[0].nodeInfo[679].positionY" 137.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[679].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[680].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[680].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[680].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[681].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[681].positionY" -7832.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[681].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[682].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[682].positionY" -3932.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[682].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[683].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[683].positionY" -422.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[683].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[684].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[684].positionY" -7832.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[684].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[685].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[685].positionY" 12967.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[685].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[686].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[686].positionY" 747.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[686].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[687].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[687].positionY" 6597.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[687].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[688].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[688].positionY" 3867.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[688].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[689].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[689].positionY" -11862.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[689].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[690].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[690].positionY" 11667.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[690].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[691].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[691].positionY" -8742.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[691].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[692].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[692].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[692].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[693].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[693].positionY" -1202.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[693].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[694].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[694].positionY" 1787.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[694].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[695].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[695].positionY" -4582.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[695].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[696].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[696].positionY" 4517.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[696].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[697].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[697].positionY" 8417.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[697].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[698].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[698].positionY" 31.428571701049805;
	setAttr ".tabGraphInfo[0].nodeInfo[698].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[699].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[699].positionY" -3542.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[699].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[700].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[700].positionY" -6792.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[700].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[701].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[701].positionY" -292.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[701].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[702].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[702].positionY" 9847.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[702].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[703].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[703].positionY" 12837.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[703].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[704].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[704].positionY" 2567.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[704].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[705].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[705].positionY" 6207.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[705].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[706].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[706].positionY" 7897.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[706].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[707].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[707].positionY" 357.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[707].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[708].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[708].positionY" -2242.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[708].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[709].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[709].positionY" -3802.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[709].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[710].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[710].positionY" -1722.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[710].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[711].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[711].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[711].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[712].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[712].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[712].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[713].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[713].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[713].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[714].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[714].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[714].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[715].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[715].positionY" 357.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[715].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[716].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[716].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[716].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[717].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[717].positionY" 2307.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[717].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[718].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[718].positionY" -1072.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[718].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[719].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[719].positionY" 2047.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[719].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[720].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[720].positionY" -1462.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[720].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[721].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[721].positionY" 5947.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[721].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[722].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[722].positionY" -7702.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[722].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[723].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[723].positionY" 357.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[723].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[724].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[724].positionY" 11147.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[724].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[725].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[725].positionY" 3867.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[725].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[726].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[726].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[726].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[727].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[727].positionY" -1982.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[727].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[728].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[728].positionY" 10757.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[728].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[729].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[729].positionY" -6272.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[729].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[730].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[730].positionY" -11472.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[730].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[731].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[731].positionY" -7442.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[731].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[732].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[732].positionY" 6987.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[732].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[733].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[733].positionY" 7507.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[733].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[734].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[734].positionY" -12772.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[734].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[735].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[735].positionY" 1917.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[735].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[736].positionX" 265.71429443359375;
	setAttr ".tabGraphInfo[0].nodeInfo[736].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[736].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[737].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[737].positionY" -4062.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[737].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[738].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[738].positionY" 227.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[738].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[739].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[739].positionY" -682.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[739].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[740].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[740].positionY" 617.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[740].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[741].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[741].positionY" -4062.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[741].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[742].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[742].positionY" 4517.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[742].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[743].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[743].positionY" -11602.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[743].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[744].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[744].positionY" -10172.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[744].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[745].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[745].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[745].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[746].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[746].positionY" 9327.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[746].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[747].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[747].positionY" -5362.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[747].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[748].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[748].positionY" -12902.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[748].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[749].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[749].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[749].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[750].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[750].positionY" -552.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[750].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[751].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[751].positionY" -7312.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[751].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[752].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[752].positionY" -7702.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[752].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[753].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[753].positionY" 2177.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[753].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[754].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[754].positionY" -9132.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[754].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[755].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[755].positionY" 1267.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[755].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[756].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[756].positionY" -6272.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[756].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[757].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[757].positionY" -1982.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[757].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[758].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[758].positionY" 7767.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[758].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[759].positionX" 68.571426391601563;
	setAttr ".tabGraphInfo[0].nodeInfo[759].positionY" 137.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[759].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[760].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[760].positionY" 10367.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[760].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[761].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[761].positionY" -942.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[761].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[762].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[762].positionY" 8157.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[762].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[763].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[763].positionY" 12447.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[763].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[764].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[764].positionY" -5232.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[764].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[765].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[765].positionY" -7962.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[765].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[766].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[766].positionY" -10822.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[766].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[767].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[767].positionY" -2762.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[767].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[768].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[768].positionY" -2892.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[768].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[769].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[769].positionY" 7247.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[769].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[770].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[770].positionY" -2762.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[770].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[771].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[771].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[771].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[772].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[772].positionY" 1527.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[772].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[773].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[773].positionY" 12057.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[773].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[774].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[774].positionY" -2112.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[774].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[775].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[775].positionY" 3087.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[775].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[776].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[776].positionY" 487.14285278320313;
	setAttr ".tabGraphInfo[0].nodeInfo[776].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[777].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[777].positionY" 3347.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[777].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[778].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[778].positionY" 6467.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[778].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[779].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[779].positionY" -32.857143402099609;
	setAttr ".tabGraphInfo[0].nodeInfo[779].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[780].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[780].positionY" -1592.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[780].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[781].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[781].positionY" -7962.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[781].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[782].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[782].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[782].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[783].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[783].positionY" 1917.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[783].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[784].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[784].positionY" -11082.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[784].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[785].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[785].positionY" -10952.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[785].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[786].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[786].positionY" -2112.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[786].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[787].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[787].positionY" -9002.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[787].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[788].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[788].positionY" 10497.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[788].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[789].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[789].positionY" 5297.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[789].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[790].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[790].positionY" 97.142860412597656;
	setAttr ".tabGraphInfo[0].nodeInfo[790].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[791].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[791].positionY" -8092.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[791].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[792].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[792].positionY" 8417.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[792].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[793].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[793].positionY" -2502.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[793].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[794].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[794].positionY" -7572.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[794].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[795].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[795].positionY" -2892.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[795].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[796].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[796].positionY" 1657.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[796].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[797].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[797].positionY" -3932.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[797].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[798].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[798].positionY" 1787.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[798].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[799].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[799].positionY" -10302.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[799].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[800].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[800].positionY" 3607.142822265625;
	setAttr ".tabGraphInfo[0].nodeInfo[800].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[801].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[801].positionY" 11927.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[801].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[802].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[802].positionY" -9652.857421875;
	setAttr ".tabGraphInfo[0].nodeInfo[802].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[803].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[803].positionY" -552.85711669921875;
	setAttr ".tabGraphInfo[0].nodeInfo[803].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[804].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[804].positionY" -2372.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[804].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[805].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[805].positionY" -3672.857177734375;
	setAttr ".tabGraphInfo[0].nodeInfo[805].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[806].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[806].positionY" 4777.14306640625;
	setAttr ".tabGraphInfo[0].nodeInfo[806].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[807].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[807].positionY" 9847.142578125;
	setAttr ".tabGraphInfo[0].nodeInfo[807].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[808].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[808].positionY" -7052.85693359375;
	setAttr ".tabGraphInfo[0].nodeInfo[808].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[809].positionX" -91.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[809].positionY" 1007.1428833007813;
	setAttr ".tabGraphInfo[0].nodeInfo[809].nodeVisualState" 18304;
select -noExpand :time1;
	setAttr ".outTime" 8;
	setAttr ".unwarpedTime" 8;
select -noExpand :hardwareRenderingGlobals;
	setAttr ".objectTypeFilterNameArray" -type "stringArray" 22 "NURBS Curves" "NURBS Surfaces" "Polygons" "Subdiv Surface" "Particles" "Particle Instance" "Fluids" "Strokes" "Image Planes" "UI" "Lights" "Cameras" "Locators" "Joints" "IK Handles" "Deformers" "Motion Trails" "Components" "Hair Systems" "Follicles" "Misc. UI" "Ornaments"  ;
	setAttr ".objectTypeFilterValueArray" -type "Int32Array" 22 0 1 1
		 1 1 1 1 1 1 0 0 0 0 0 0
		 0 0 0 0 0 0 0 ;
	setAttr ".floatingPointRTEnable" yes;
select -noExpand :renderPartition;
	setAttr -size 4 ".sets";
select -noExpand :renderGlobalsList1;
select -noExpand :defaultShaderList1;
	setAttr -size 6 ".shaders";
select -noExpand :postProcessList1;
	setAttr -size 2 ".postProcesses";
select -noExpand :defaultRenderingList1;
select -noExpand :initialShadingGroup;
	setAttr ".renderableOnlySet" yes;
select -noExpand :initialParticleSE;
	setAttr ".renderableOnlySet" yes;
select -noExpand :defaultRenderGlobals;
	setAttr ".comFrrt" 30;
	setAttr ".startFrame" 1;
	setAttr ".endFrame" 10;
select -noExpand :defaultResolution;
	setAttr ".pixelAspect" 1;
select -noExpand :hardwareRenderGlobals;
	setAttr ".colorTextureResolution" 256;
	setAttr ".bumpTextureResolution" 512;
	setAttr ".hardwareFrameRate" 30;
connectAttr "mPyNode1.position[0]" "boid0.translate";
connectAttr "polyCube1.output" "boidShape0.inMesh";
connectAttr "mPyNode1.position[1]" "boid1.translate";
connectAttr "mPyNode1.position[2]" "boid2.translate";
connectAttr "mPyNode1.position[3]" "boid3.translate";
connectAttr "mPyNode1.position[4]" "boid4.translate";
connectAttr "mPyNode1.position[5]" "boid5.translate";
connectAttr "mPyNode1.position[6]" "boid6.translate";
connectAttr "mPyNode1.position[7]" "boid7.translate";
connectAttr "mPyNode1.position[8]" "boid8.translate";
connectAttr "mPyNode1.position[9]" "boid9.translate";
connectAttr "mPyNode1.position[10]" "boid10.translate";
connectAttr "mPyNode1.position[11]" "boid11.translate";
connectAttr "mPyNode1.position[12]" "boid12.translate";
connectAttr "mPyNode1.position[13]" "boid13.translate";
connectAttr "mPyNode1.position[14]" "boid14.translate";
connectAttr "mPyNode1.position[15]" "boid15.translate";
connectAttr "mPyNode1.position[16]" "boid16.translate";
connectAttr "mPyNode1.position[17]" "boid17.translate";
connectAttr "mPyNode1.position[18]" "boid18.translate";
connectAttr "mPyNode1.position[19]" "boid19.translate";
connectAttr "mPyNode1.position[20]" "boid20.translate";
connectAttr "mPyNode1.position[21]" "boid21.translate";
connectAttr "mPyNode1.position[22]" "boid22.translate";
connectAttr "mPyNode1.position[23]" "boid23.translate";
connectAttr "mPyNode1.position[24]" "boid24.translate";
connectAttr "mPyNode1.position[25]" "boid25.translate";
connectAttr "mPyNode1.position[26]" "boid26.translate";
connectAttr "mPyNode1.position[27]" "boid27.translate";
connectAttr "mPyNode1.position[28]" "boid28.translate";
connectAttr "mPyNode1.position[29]" "boid29.translate";
connectAttr "mPyNode1.position[30]" "boid30.translate";
connectAttr "mPyNode1.position[31]" "boid31.translate";
connectAttr "mPyNode1.position[32]" "boid32.translate";
connectAttr "mPyNode1.position[33]" "boid33.translate";
connectAttr "mPyNode1.position[34]" "boid34.translate";
connectAttr "mPyNode1.position[35]" "boid35.translate";
connectAttr "mPyNode1.position[36]" "boid36.translate";
connectAttr "mPyNode1.position[37]" "boid37.translate";
connectAttr "mPyNode1.position[38]" "boid38.translate";
connectAttr "mPyNode1.position[39]" "boid39.translate";
connectAttr "mPyNode1.position[40]" "boid40.translate";
connectAttr "mPyNode1.position[41]" "boid41.translate";
connectAttr "mPyNode1.position[42]" "boid42.translate";
connectAttr "mPyNode1.position[43]" "boid43.translate";
connectAttr "mPyNode1.position[44]" "boid44.translate";
connectAttr "mPyNode1.position[45]" "boid45.translate";
connectAttr "mPyNode1.position[46]" "boid46.translate";
connectAttr "mPyNode1.position[47]" "boid47.translate";
connectAttr "mPyNode1.position[48]" "boid48.translate";
connectAttr "mPyNode1.position[49]" "boid49.translate";
connectAttr "mPyNode1.position[50]" "boid50.translate";
connectAttr "mPyNode1.position[51]" "boid51.translate";
connectAttr "mPyNode1.position[52]" "boid52.translate";
connectAttr "mPyNode1.position[53]" "boid53.translate";
connectAttr "mPyNode1.position[54]" "boid54.translate";
connectAttr "mPyNode1.position[55]" "boid55.translate";
connectAttr "mPyNode1.position[56]" "boid56.translate";
connectAttr "mPyNode1.position[57]" "boid57.translate";
connectAttr "mPyNode1.position[58]" "boid58.translate";
connectAttr "mPyNode1.position[59]" "boid59.translate";
connectAttr "mPyNode1.position[60]" "boid60.translate";
connectAttr "mPyNode1.position[61]" "boid61.translate";
connectAttr "mPyNode1.position[62]" "boid62.translate";
connectAttr "mPyNode1.position[63]" "boid63.translate";
connectAttr "mPyNode1.position[64]" "boid64.translate";
connectAttr "mPyNode1.position[65]" "boid65.translate";
connectAttr "mPyNode1.position[66]" "boid66.translate";
connectAttr "mPyNode1.position[67]" "boid67.translate";
connectAttr "mPyNode1.position[68]" "boid68.translate";
connectAttr "mPyNode1.position[69]" "boid69.translate";
connectAttr "mPyNode1.position[70]" "boid70.translate";
connectAttr "mPyNode1.position[71]" "boid71.translate";
connectAttr "mPyNode1.position[72]" "boid72.translate";
connectAttr "mPyNode1.position[73]" "boid73.translate";
connectAttr "mPyNode1.position[74]" "boid74.translate";
connectAttr "mPyNode1.position[75]" "boid75.translate";
connectAttr "mPyNode1.position[76]" "boid76.translate";
connectAttr "mPyNode1.position[77]" "boid77.translate";
connectAttr "mPyNode1.position[78]" "boid78.translate";
connectAttr "mPyNode1.position[79]" "boid79.translate";
connectAttr "mPyNode1.position[80]" "boid80.translate";
connectAttr "mPyNode1.position[81]" "boid81.translate";
connectAttr "mPyNode1.position[82]" "boid82.translate";
connectAttr "mPyNode1.position[83]" "boid83.translate";
connectAttr "mPyNode1.position[84]" "boid84.translate";
connectAttr "mPyNode1.position[85]" "boid85.translate";
connectAttr "mPyNode1.position[86]" "boid86.translate";
connectAttr "mPyNode1.position[87]" "boid87.translate";
connectAttr "mPyNode1.position[88]" "boid88.translate";
connectAttr "mPyNode1.position[89]" "boid89.translate";
connectAttr "mPyNode1.position[90]" "boid90.translate";
connectAttr "mPyNode1.position[91]" "boid91.translate";
connectAttr "mPyNode1.position[92]" "boid92.translate";
connectAttr "mPyNode1.position[93]" "boid93.translate";
connectAttr "mPyNode1.position[94]" "boid94.translate";
connectAttr "mPyNode1.position[95]" "boid95.translate";
connectAttr "mPyNode1.position[96]" "boid96.translate";
connectAttr "mPyNode1.position[97]" "boid97.translate";
connectAttr "mPyNode1.position[98]" "boid98.translate";
connectAttr "mPyNode1.position[99]" "boid99.translate";
connectAttr "mPyNode1.position[100]" "boid100.translate";
connectAttr "mPyNode1.position[101]" "boid101.translate";
connectAttr "mPyNode1.position[102]" "boid102.translate";
connectAttr "mPyNode1.position[103]" "boid103.translate";
connectAttr "mPyNode1.position[104]" "boid104.translate";
connectAttr "mPyNode1.position[105]" "boid105.translate";
connectAttr "mPyNode1.position[106]" "boid106.translate";
connectAttr "mPyNode1.position[107]" "boid107.translate";
connectAttr "mPyNode1.position[108]" "boid108.translate";
connectAttr "mPyNode1.position[109]" "boid109.translate";
connectAttr "mPyNode1.position[110]" "boid110.translate";
connectAttr "mPyNode1.position[111]" "boid111.translate";
connectAttr "mPyNode1.position[112]" "boid112.translate";
connectAttr "mPyNode1.position[113]" "boid113.translate";
connectAttr "mPyNode1.position[114]" "boid114.translate";
connectAttr "mPyNode1.position[115]" "boid115.translate";
connectAttr "mPyNode1.position[116]" "boid116.translate";
connectAttr "mPyNode1.position[117]" "boid117.translate";
connectAttr "mPyNode1.position[118]" "boid118.translate";
connectAttr "mPyNode1.position[119]" "boid119.translate";
connectAttr "mPyNode1.position[120]" "boid120.translate";
connectAttr "mPyNode1.position[121]" "boid121.translate";
connectAttr "mPyNode1.position[122]" "boid122.translate";
connectAttr "mPyNode1.position[123]" "boid123.translate";
connectAttr "mPyNode1.position[124]" "boid124.translate";
connectAttr "mPyNode1.position[125]" "boid125.translate";
connectAttr "mPyNode1.position[126]" "boid126.translate";
connectAttr "mPyNode1.position[127]" "boid127.translate";
connectAttr "mPyNode1.position[128]" "boid128.translate";
connectAttr "mPyNode1.position[129]" "boid129.translate";
connectAttr "mPyNode1.position[130]" "boid130.translate";
connectAttr "mPyNode1.position[131]" "boid131.translate";
connectAttr "mPyNode1.position[132]" "boid132.translate";
connectAttr "mPyNode1.position[133]" "boid133.translate";
connectAttr "mPyNode1.position[134]" "boid134.translate";
connectAttr "mPyNode1.position[135]" "boid135.translate";
connectAttr "mPyNode1.position[136]" "boid136.translate";
connectAttr "mPyNode1.position[137]" "boid137.translate";
connectAttr "mPyNode1.position[138]" "boid138.translate";
connectAttr "mPyNode1.position[139]" "boid139.translate";
connectAttr "mPyNode1.position[140]" "boid140.translate";
connectAttr "mPyNode1.position[141]" "boid141.translate";
connectAttr "mPyNode1.position[142]" "boid142.translate";
connectAttr "mPyNode1.position[143]" "boid143.translate";
connectAttr "mPyNode1.position[144]" "boid144.translate";
connectAttr "mPyNode1.position[145]" "boid145.translate";
connectAttr "mPyNode1.position[146]" "boid146.translate";
connectAttr "mPyNode1.position[147]" "boid147.translate";
connectAttr "mPyNode1.position[148]" "boid148.translate";
connectAttr "mPyNode1.position[149]" "boid149.translate";
connectAttr "mPyNode1.position[150]" "boid150.translate";
connectAttr "mPyNode1.position[151]" "boid151.translate";
connectAttr "mPyNode1.position[152]" "boid152.translate";
connectAttr "mPyNode1.position[153]" "boid153.translate";
connectAttr "mPyNode1.position[154]" "boid154.translate";
connectAttr "mPyNode1.position[155]" "boid155.translate";
connectAttr "mPyNode1.position[156]" "boid156.translate";
connectAttr "mPyNode1.position[157]" "boid157.translate";
connectAttr "mPyNode1.position[158]" "boid158.translate";
connectAttr "mPyNode1.position[159]" "boid159.translate";
connectAttr "mPyNode1.position[160]" "boid160.translate";
connectAttr "mPyNode1.position[161]" "boid161.translate";
connectAttr "mPyNode1.position[162]" "boid162.translate";
connectAttr "mPyNode1.position[163]" "boid163.translate";
connectAttr "mPyNode1.position[164]" "boid164.translate";
connectAttr "mPyNode1.position[165]" "boid165.translate";
connectAttr "mPyNode1.position[166]" "boid166.translate";
connectAttr "mPyNode1.position[167]" "boid167.translate";
connectAttr "mPyNode1.position[168]" "boid168.translate";
connectAttr "mPyNode1.position[169]" "boid169.translate";
connectAttr "mPyNode1.position[170]" "boid170.translate";
connectAttr "mPyNode1.position[171]" "boid171.translate";
connectAttr "mPyNode1.position[172]" "boid172.translate";
connectAttr "mPyNode1.position[173]" "boid173.translate";
connectAttr "mPyNode1.position[174]" "boid174.translate";
connectAttr "mPyNode1.position[175]" "boid175.translate";
connectAttr "mPyNode1.position[176]" "boid176.translate";
connectAttr "mPyNode1.position[177]" "boid177.translate";
connectAttr "mPyNode1.position[178]" "boid178.translate";
connectAttr "mPyNode1.position[179]" "boid179.translate";
connectAttr "mPyNode1.position[180]" "boid180.translate";
connectAttr "mPyNode1.position[181]" "boid181.translate";
connectAttr "mPyNode1.position[182]" "boid182.translate";
connectAttr "mPyNode1.position[183]" "boid183.translate";
connectAttr "mPyNode1.position[184]" "boid184.translate";
connectAttr "mPyNode1.position[185]" "boid185.translate";
connectAttr "mPyNode1.position[186]" "boid186.translate";
connectAttr "mPyNode1.position[187]" "boid187.translate";
connectAttr "mPyNode1.position[188]" "boid188.translate";
connectAttr "mPyNode1.position[189]" "boid189.translate";
connectAttr "mPyNode1.position[190]" "boid190.translate";
connectAttr "mPyNode1.position[191]" "boid191.translate";
connectAttr "mPyNode1.position[192]" "boid192.translate";
connectAttr "mPyNode1.position[193]" "boid193.translate";
connectAttr "mPyNode1.position[194]" "boid194.translate";
connectAttr "mPyNode1.position[195]" "boid195.translate";
connectAttr "mPyNode1.position[196]" "boid196.translate";
connectAttr "mPyNode1.position[197]" "boid197.translate";
connectAttr "mPyNode1.position[198]" "boid198.translate";
connectAttr "mPyNode1.position[199]" "boid199.translate";
connectAttr "mPyNode1.position[200]" "boid200.translate";
connectAttr "mPyNode1.position[201]" "boid201.translate";
connectAttr "mPyNode1.position[202]" "boid202.translate";
connectAttr "mPyNode1.position[203]" "boid203.translate";
connectAttr "mPyNode1.position[204]" "boid204.translate";
connectAttr "mPyNode1.position[205]" "boid205.translate";
connectAttr "mPyNode1.position[206]" "boid206.translate";
connectAttr "mPyNode1.position[207]" "boid207.translate";
connectAttr "mPyNode1.position[208]" "boid208.translate";
connectAttr "mPyNode1.position[209]" "boid209.translate";
connectAttr "mPyNode1.position[210]" "boid210.translate";
connectAttr "mPyNode1.position[211]" "boid211.translate";
connectAttr "mPyNode1.position[212]" "boid212.translate";
connectAttr "mPyNode1.position[213]" "boid213.translate";
connectAttr "mPyNode1.position[214]" "boid214.translate";
connectAttr "mPyNode1.position[215]" "boid215.translate";
connectAttr "mPyNode1.position[216]" "boid216.translate";
connectAttr "mPyNode1.position[217]" "boid217.translate";
connectAttr "mPyNode1.position[218]" "boid218.translate";
connectAttr "mPyNode1.position[219]" "boid219.translate";
connectAttr "mPyNode1.position[220]" "boid220.translate";
connectAttr "mPyNode1.position[221]" "boid221.translate";
connectAttr "mPyNode1.position[222]" "boid222.translate";
connectAttr "mPyNode1.position[223]" "boid223.translate";
connectAttr "mPyNode1.position[224]" "boid224.translate";
connectAttr "mPyNode1.position[225]" "boid225.translate";
connectAttr "mPyNode1.position[226]" "boid226.translate";
connectAttr "mPyNode1.position[227]" "boid227.translate";
connectAttr "mPyNode1.position[228]" "boid228.translate";
connectAttr "mPyNode1.position[229]" "boid229.translate";
connectAttr "mPyNode1.position[230]" "boid230.translate";
connectAttr "mPyNode1.position[231]" "boid231.translate";
connectAttr "mPyNode1.position[232]" "boid232.translate";
connectAttr "mPyNode1.position[233]" "boid233.translate";
connectAttr "mPyNode1.position[234]" "boid234.translate";
connectAttr "mPyNode1.position[235]" "boid235.translate";
connectAttr "mPyNode1.position[236]" "boid236.translate";
connectAttr "mPyNode1.position[237]" "boid237.translate";
connectAttr "mPyNode1.position[238]" "boid238.translate";
connectAttr "mPyNode1.position[239]" "boid239.translate";
connectAttr "mPyNode1.position[240]" "boid240.translate";
connectAttr "mPyNode1.position[241]" "boid241.translate";
connectAttr "mPyNode1.position[242]" "boid242.translate";
connectAttr "mPyNode1.position[243]" "boid243.translate";
connectAttr "mPyNode1.position[244]" "boid244.translate";
connectAttr "mPyNode1.position[245]" "boid245.translate";
connectAttr "mPyNode1.position[246]" "boid246.translate";
connectAttr "mPyNode1.position[247]" "boid247.translate";
connectAttr "mPyNode1.position[248]" "boid248.translate";
connectAttr "mPyNode1.position[249]" "boid249.translate";
connectAttr "mPyNode1.position[250]" "boid250.translate";
connectAttr "mPyNode1.position[251]" "boid251.translate";
connectAttr "mPyNode1.position[252]" "boid252.translate";
connectAttr "mPyNode1.position[253]" "boid253.translate";
connectAttr "mPyNode1.position[254]" "boid254.translate";
connectAttr "mPyNode1.position[255]" "boid255.translate";
connectAttr "mPyNode1.position[256]" "boid256.translate";
connectAttr "mPyNode1.position[257]" "boid257.translate";
connectAttr "mPyNode1.position[258]" "boid258.translate";
connectAttr "mPyNode1.position[259]" "boid259.translate";
connectAttr "mPyNode1.position[260]" "boid260.translate";
connectAttr "mPyNode1.position[261]" "boid261.translate";
connectAttr "mPyNode1.position[262]" "boid262.translate";
connectAttr "mPyNode1.position[263]" "boid263.translate";
connectAttr "mPyNode1.position[264]" "boid264.translate";
connectAttr "mPyNode1.position[265]" "boid265.translate";
connectAttr "mPyNode1.position[266]" "boid266.translate";
connectAttr "mPyNode1.position[267]" "boid267.translate";
connectAttr "mPyNode1.position[268]" "boid268.translate";
connectAttr "mPyNode1.position[269]" "boid269.translate";
connectAttr "mPyNode1.position[270]" "boid270.translate";
connectAttr "mPyNode1.position[271]" "boid271.translate";
connectAttr "mPyNode1.position[272]" "boid272.translate";
connectAttr "mPyNode1.position[273]" "boid273.translate";
connectAttr "mPyNode1.position[274]" "boid274.translate";
connectAttr "mPyNode1.position[275]" "boid275.translate";
connectAttr "mPyNode1.position[276]" "boid276.translate";
connectAttr "mPyNode1.position[277]" "boid277.translate";
connectAttr "mPyNode1.position[278]" "boid278.translate";
connectAttr "mPyNode1.position[279]" "boid279.translate";
connectAttr "mPyNode1.position[280]" "boid280.translate";
connectAttr "mPyNode1.position[281]" "boid281.translate";
connectAttr "mPyNode1.position[282]" "boid282.translate";
connectAttr "mPyNode1.position[283]" "boid283.translate";
connectAttr "mPyNode1.position[284]" "boid284.translate";
connectAttr "mPyNode1.position[285]" "boid285.translate";
connectAttr "mPyNode1.position[286]" "boid286.translate";
connectAttr "mPyNode1.position[287]" "boid287.translate";
connectAttr "mPyNode1.position[288]" "boid288.translate";
connectAttr "mPyNode1.position[289]" "boid289.translate";
connectAttr "mPyNode1.position[290]" "boid290.translate";
connectAttr "mPyNode1.position[291]" "boid291.translate";
connectAttr "mPyNode1.position[292]" "boid292.translate";
connectAttr "mPyNode1.position[293]" "boid293.translate";
connectAttr "mPyNode1.position[294]" "boid294.translate";
connectAttr "mPyNode1.position[295]" "boid295.translate";
connectAttr "mPyNode1.position[296]" "boid296.translate";
connectAttr "mPyNode1.position[297]" "boid297.translate";
connectAttr "mPyNode1.position[298]" "boid298.translate";
connectAttr "mPyNode1.position[299]" "boid299.translate";
connectAttr "mPyNode1.position[300]" "boid300.translate";
connectAttr "mPyNode1.position[301]" "boid301.translate";
connectAttr "mPyNode1.position[302]" "boid302.translate";
connectAttr "mPyNode1.position[303]" "boid303.translate";
connectAttr "mPyNode1.position[304]" "boid304.translate";
connectAttr "mPyNode1.position[305]" "boid305.translate";
connectAttr "mPyNode1.position[306]" "boid306.translate";
connectAttr "mPyNode1.position[307]" "boid307.translate";
connectAttr "mPyNode1.position[308]" "boid308.translate";
connectAttr "mPyNode1.position[309]" "boid309.translate";
connectAttr "mPyNode1.position[310]" "boid310.translate";
connectAttr "mPyNode1.position[311]" "boid311.translate";
connectAttr "mPyNode1.position[312]" "boid312.translate";
connectAttr "mPyNode1.position[313]" "boid313.translate";
connectAttr "mPyNode1.position[314]" "boid314.translate";
connectAttr "mPyNode1.position[315]" "boid315.translate";
connectAttr "mPyNode1.position[316]" "boid316.translate";
connectAttr "mPyNode1.position[317]" "boid317.translate";
connectAttr "mPyNode1.position[318]" "boid318.translate";
connectAttr "mPyNode1.position[319]" "boid319.translate";
connectAttr "mPyNode1.position[320]" "boid320.translate";
connectAttr "mPyNode1.position[321]" "boid321.translate";
connectAttr "mPyNode1.position[322]" "boid322.translate";
connectAttr "mPyNode1.position[323]" "boid323.translate";
connectAttr "mPyNode1.position[324]" "boid324.translate";
connectAttr "mPyNode1.position[325]" "boid325.translate";
connectAttr "mPyNode1.position[326]" "boid326.translate";
connectAttr "mPyNode1.position[327]" "boid327.translate";
connectAttr "mPyNode1.position[328]" "boid328.translate";
connectAttr "mPyNode1.position[329]" "boid329.translate";
connectAttr "mPyNode1.position[330]" "boid330.translate";
connectAttr "mPyNode1.position[331]" "boid331.translate";
connectAttr "mPyNode1.position[332]" "boid332.translate";
connectAttr "mPyNode1.position[333]" "boid333.translate";
connectAttr "mPyNode1.position[334]" "boid334.translate";
connectAttr "mPyNode1.position[335]" "boid335.translate";
connectAttr "mPyNode1.position[336]" "boid336.translate";
connectAttr "mPyNode1.position[337]" "boid337.translate";
connectAttr "mPyNode1.position[338]" "boid338.translate";
connectAttr "mPyNode1.position[339]" "boid339.translate";
connectAttr "mPyNode1.position[340]" "boid340.translate";
connectAttr "mPyNode1.position[341]" "boid341.translate";
connectAttr "mPyNode1.position[342]" "boid342.translate";
connectAttr "mPyNode1.position[343]" "boid343.translate";
connectAttr "mPyNode1.position[344]" "boid344.translate";
connectAttr "mPyNode1.position[345]" "boid345.translate";
connectAttr "mPyNode1.position[346]" "boid346.translate";
connectAttr "mPyNode1.position[347]" "boid347.translate";
connectAttr "mPyNode1.position[348]" "boid348.translate";
connectAttr "mPyNode1.position[349]" "boid349.translate";
connectAttr "mPyNode1.position[350]" "boid350.translate";
connectAttr "mPyNode1.position[351]" "boid351.translate";
connectAttr "mPyNode1.position[352]" "boid352.translate";
connectAttr "mPyNode1.position[353]" "boid353.translate";
connectAttr "mPyNode1.position[354]" "boid354.translate";
connectAttr "mPyNode1.position[355]" "boid355.translate";
connectAttr "mPyNode1.position[356]" "boid356.translate";
connectAttr "mPyNode1.position[357]" "boid357.translate";
connectAttr "mPyNode1.position[358]" "boid358.translate";
connectAttr "mPyNode1.position[359]" "boid359.translate";
connectAttr "mPyNode1.position[360]" "boid360.translate";
connectAttr "mPyNode1.position[361]" "boid361.translate";
connectAttr "mPyNode1.position[362]" "boid362.translate";
connectAttr "mPyNode1.position[363]" "boid363.translate";
connectAttr "mPyNode1.position[364]" "boid364.translate";
connectAttr "mPyNode1.position[365]" "boid365.translate";
connectAttr "mPyNode1.position[366]" "boid366.translate";
connectAttr "mPyNode1.position[367]" "boid367.translate";
connectAttr "mPyNode1.position[368]" "boid368.translate";
connectAttr "mPyNode1.position[369]" "boid369.translate";
connectAttr "mPyNode1.position[370]" "boid370.translate";
connectAttr "mPyNode1.position[371]" "boid371.translate";
connectAttr "mPyNode1.position[372]" "boid372.translate";
connectAttr "mPyNode1.position[373]" "boid373.translate";
connectAttr "mPyNode1.position[374]" "boid374.translate";
connectAttr "mPyNode1.position[375]" "boid375.translate";
connectAttr "mPyNode1.position[376]" "boid376.translate";
connectAttr "mPyNode1.position[377]" "boid377.translate";
connectAttr "mPyNode1.position[378]" "boid378.translate";
connectAttr "mPyNode1.position[379]" "boid379.translate";
connectAttr "mPyNode1.position[380]" "boid380.translate";
connectAttr "mPyNode1.position[381]" "boid381.translate";
connectAttr "mPyNode1.position[382]" "boid382.translate";
connectAttr "mPyNode1.position[383]" "boid383.translate";
connectAttr "mPyNode1.position[384]" "boid384.translate";
connectAttr "mPyNode1.position[385]" "boid385.translate";
connectAttr "mPyNode1.position[386]" "boid386.translate";
connectAttr "mPyNode1.position[387]" "boid387.translate";
connectAttr "mPyNode1.position[388]" "boid388.translate";
connectAttr "mPyNode1.position[389]" "boid389.translate";
connectAttr "mPyNode1.position[390]" "boid390.translate";
connectAttr "mPyNode1.position[391]" "boid391.translate";
connectAttr "mPyNode1.position[392]" "boid392.translate";
connectAttr "mPyNode1.position[393]" "boid393.translate";
connectAttr "mPyNode1.position[394]" "boid394.translate";
connectAttr "mPyNode1.position[395]" "boid395.translate";
connectAttr "mPyNode1.position[396]" "boid396.translate";
connectAttr "mPyNode1.position[397]" "boid397.translate";
connectAttr "mPyNode1.position[398]" "boid398.translate";
connectAttr "mPyNode1.position[399]" "boid399.translate";
relationship "link" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "link" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
relationship "link" ":lightLinker1" "blinn1SG.message" ":defaultLightSet.message";
relationship "link" ":lightLinker1" "blinn2SG.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" "blinn1SG.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" "blinn2SG.message" ":defaultLightSet.message";
connectAttr "layerManager.displayLayerId[0]" "defaultLayer.identification";
connectAttr "renderLayerManager.renderLayerId[0]" "defaultRenderLayer.identification"
		;
connectAttr "blinn1.outColor" "blinn1SG.surfaceShader";
connectAttr "blinn1SG.message" "materialInfo1.shadingGroup";
connectAttr "blinn1.message" "materialInfo1.material";
connectAttr "blinn2.outColor" "blinn2SG.surfaceShader";
connectAttr "boidShape11.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape12.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape16.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape17.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape13.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape14.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape15.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape32.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape33.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape34.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape35.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape36.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape37.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape38.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape39.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape40.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape41.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape42.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape43.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape44.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape45.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape46.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape47.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape48.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape49.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape50.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape51.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape52.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape53.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape54.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape55.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape56.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape57.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape58.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape59.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape100.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape101.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape300.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape301.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape302.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape303.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape304.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape305.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape306.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape307.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape308.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape211.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape212.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape213.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape214.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape215.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape216.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape217.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape218.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape219.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape220.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape221.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape234.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape235.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape236.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape237.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape238.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape239.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape240.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape241.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape242.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape243.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape244.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape245.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape246.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape222.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape223.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape224.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape225.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape226.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape227.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape228.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape229.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape230.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape231.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape232.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape233.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape247.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape248.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape249.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape250.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape251.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape252.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape253.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape254.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape255.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape256.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape257.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape258.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape259.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape260.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape261.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape262.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape263.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape264.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape265.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape266.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape267.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape268.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape269.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape270.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape271.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape80.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape81.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape82.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape83.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape84.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape85.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape163.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape164.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape165.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape166.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape167.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape168.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape169.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape170.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape171.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape172.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape173.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape174.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape175.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape151.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape152.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape153.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape154.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape155.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape156.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape157.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape158.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape159.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape160.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape161.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape162.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape188.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape189.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape190.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape191.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape192.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape193.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape194.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape195.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape196.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape197.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape198.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape199.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape176.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape177.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape178.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape179.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape180.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape181.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape182.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape183.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape184.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape185.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape186.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape187.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape115.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape116.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape117.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape118.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape119.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape120.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape121.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape122.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape123.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape124.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape125.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape102.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape103.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape104.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape105.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape106.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape107.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape108.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape109.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape110.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape111.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape112.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape113.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape114.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape126.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape127.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape128.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape129.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape130.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape131.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape132.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape133.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape134.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape135.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape136.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape137.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape138.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape139.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape140.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape141.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape142.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape143.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape144.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape145.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape146.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape147.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape148.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape149.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape150.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape309.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape310.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape311.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape312.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape313.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape314.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape315.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape316.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape317.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape318.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape319.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape320.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape321.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape322.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape323.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape324.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape325.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape326.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape327.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape328.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape329.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape330.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape331.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape332.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape345.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape346.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape347.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape348.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape349.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape350.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape351.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape352.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape353.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape354.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape355.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape356.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape357.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape333.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape334.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape335.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape336.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape337.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape338.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape339.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape340.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape341.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape342.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape343.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape344.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape370.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape371.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape372.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape373.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape374.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape375.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape376.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape377.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape378.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape379.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape380.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape381.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape382.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape358.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape359.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape360.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape361.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape362.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape363.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape364.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape365.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape366.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape367.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape368.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape369.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape383.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape384.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape385.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape386.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape387.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape388.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape389.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape390.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape391.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape392.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape393.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape394.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape395.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape396.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape397.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape398.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape399.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape0.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape4.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape5.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape6.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape7.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape8.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape18.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape19.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape20.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape21.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape22.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape23.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape24.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape25.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape26.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape27.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape28.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape29.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape30.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape31.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape60.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape61.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape62.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape63.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape64.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape65.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape66.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape67.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape1.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape9.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape10.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape86.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape87.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape88.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape89.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape90.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape91.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape92.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape93.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape94.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape95.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape96.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape97.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape98.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape99.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape200.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape201.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape202.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape203.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape204.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape205.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape206.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape207.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape208.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape209.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape210.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape79.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape68.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape69.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape70.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape71.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape72.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape73.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape74.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape75.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape76.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape77.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape78.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape272.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape273.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape274.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape275.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape276.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape277.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape278.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape279.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape280.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape281.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape282.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape283.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape297.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape298.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape299.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape284.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape285.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape286.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape287.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape288.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape289.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape290.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape291.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape292.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape293.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape294.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape295.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape296.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable
		;
connectAttr "boidShape2.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "boidShape3.instObjGroups" "blinn2SG.dagSetMembers" -nextAvailable;
connectAttr "blinn2SG.message" "materialInfo2.shadingGroup";
connectAttr "blinn2.message" "materialInfo2.material";
connectAttr ":time1.outTime" "mPyNode1.time";
connectAttr "blinn2.message" "hyperShadePrimaryNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[0].dependNode"
		;
connectAttr "blinn1SG.message" "hyperShadePrimaryNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[1].dependNode"
		;
connectAttr "blinn2SG.message" "hyperShadePrimaryNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[2].dependNode"
		;
connectAttr "blinn1.message" "hyperShadePrimaryNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[3].dependNode"
		;
connectAttr "boidShape241.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[0].dependNode"
		;
connectAttr "boid18.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[1].dependNode"
		;
connectAttr "boidShape189.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[2].dependNode"
		;
connectAttr "boid104.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[3].dependNode"
		;
connectAttr "boidShape81.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[4].dependNode"
		;
connectAttr "boidShape360.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[5].dependNode"
		;
connectAttr "boidShape159.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[6].dependNode"
		;
connectAttr "boidShape31.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[7].dependNode"
		;
connectAttr "boid143.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[8].dependNode"
		;
connectAttr "boidShape387.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[9].dependNode"
		;
connectAttr "boidShape168.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[10].dependNode"
		;
connectAttr "boidShape226.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[11].dependNode"
		;
connectAttr "boidShape183.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[12].dependNode"
		;
connectAttr "boidShape24.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[13].dependNode"
		;
connectAttr "boidShape336.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[14].dependNode"
		;
connectAttr "boidShape341.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[15].dependNode"
		;
connectAttr "boid238.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[16].dependNode"
		;
connectAttr "boid138.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[17].dependNode"
		;
connectAttr "boidShape166.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[18].dependNode"
		;
connectAttr "boidShape236.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[19].dependNode"
		;
connectAttr "boidShape193.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[20].dependNode"
		;
connectAttr "boidShape361.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[21].dependNode"
		;
connectAttr "boid316.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[22].dependNode"
		;
connectAttr "boidShape335.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[23].dependNode"
		;
connectAttr "boidShape366.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[24].dependNode"
		;
connectAttr "boidShape130.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[25].dependNode"
		;
connectAttr "boid276.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[26].dependNode"
		;
connectAttr "boidShape175.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[27].dependNode"
		;
connectAttr "boidShape376.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[28].dependNode"
		;
connectAttr "boid192.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[29].dependNode"
		;
connectAttr "boidShape351.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[30].dependNode"
		;
connectAttr "boidShape162.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[31].dependNode"
		;
connectAttr "boid289.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[32].dependNode"
		;
connectAttr "boidShape220.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[33].dependNode"
		;
connectAttr "boid187.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[34].dependNode"
		;
connectAttr "boidShape252.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[35].dependNode"
		;
connectAttr "boid154.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[36].dependNode"
		;
connectAttr "boidShape196.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[37].dependNode"
		;
connectAttr "boid153.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[38].dependNode"
		;
connectAttr "boid161.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[39].dependNode"
		;
connectAttr "boid396.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[40].dependNode"
		;
connectAttr "boidShape104.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[41].dependNode"
		;
connectAttr "boidShape181.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[42].dependNode"
		;
connectAttr "boid325.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[43].dependNode"
		;
connectAttr "boidShape60.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[44].dependNode"
		;
connectAttr "boidShape141.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[45].dependNode"
		;
connectAttr "boidShape289.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[46].dependNode"
		;
connectAttr "boid80.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[47].dependNode"
		;
connectAttr "boidShape90.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[48].dependNode"
		;
connectAttr "boidShape71.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[49].dependNode"
		;
connectAttr "boidShape133.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[50].dependNode"
		;
connectAttr "boid302.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[51].dependNode"
		;
connectAttr "boidShape170.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[52].dependNode"
		;
connectAttr "boidShape77.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[53].dependNode"
		;
connectAttr "boid271.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[54].dependNode"
		;
connectAttr "boid8.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[55].dependNode"
		;
connectAttr "boid224.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[56].dependNode"
		;
connectAttr "boidShape139.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[57].dependNode"
		;
connectAttr "boid21.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[58].dependNode"
		;
connectAttr "boid152.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[59].dependNode"
		;
connectAttr "boid174.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[60].dependNode"
		;
connectAttr "boidShape320.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[61].dependNode"
		;
connectAttr "boid281.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[62].dependNode"
		;
connectAttr "boidShape35.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[63].dependNode"
		;
connectAttr "boid194.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[64].dependNode"
		;
connectAttr "boid247.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[65].dependNode"
		;
connectAttr "boidShape274.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[66].dependNode"
		;
connectAttr "boid291.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[67].dependNode"
		;
connectAttr "boid168.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[68].dependNode"
		;
connectAttr "boid260.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[69].dependNode"
		;
connectAttr "boid196.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[70].dependNode"
		;
connectAttr "boid43.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[71].dependNode"
		;
connectAttr "boidShape146.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[72].dependNode"
		;
connectAttr "boidShape15.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[73].dependNode"
		;
connectAttr "boidShape29.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[74].dependNode"
		;
connectAttr "boid66.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[75].dependNode"
		;
connectAttr "boid365.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[76].dependNode"
		;
connectAttr "boidShape150.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[77].dependNode"
		;
connectAttr "boid17.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[78].dependNode"
		;
connectAttr "boid336.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[79].dependNode"
		;
connectAttr "boidShape184.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[80].dependNode"
		;
connectAttr "boid164.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[81].dependNode"
		;
connectAttr "boidShape50.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[82].dependNode"
		;
connectAttr "boid231.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[83].dependNode"
		;
connectAttr "boidShape261.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[84].dependNode"
		;
connectAttr "boid31.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[85].dependNode"
		;
connectAttr "boidShape138.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[86].dependNode"
		;
connectAttr "boid159.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[87].dependNode"
		;
connectAttr "boid298.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[88].dependNode"
		;
connectAttr "boidShape112.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[89].dependNode"
		;
connectAttr "boid214.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[90].dependNode"
		;
connectAttr "boidShape38.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[91].dependNode"
		;
connectAttr "boid86.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[92].dependNode"
		;
connectAttr "boid374.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[93].dependNode"
		;
connectAttr "boid145.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[94].dependNode"
		;
connectAttr "boidShape1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[95].dependNode"
		;
connectAttr "boidShape300.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[96].dependNode"
		;
connectAttr "boid318.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[97].dependNode"
		;
connectAttr "boidShape84.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[98].dependNode"
		;
connectAttr "boidShape79.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[99].dependNode"
		;
connectAttr "boid77.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[100].dependNode"
		;
connectAttr "boid345.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[101].dependNode"
		;
connectAttr "boid397.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[102].dependNode"
		;
connectAttr "boid24.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[103].dependNode"
		;
connectAttr "boidShape178.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[104].dependNode"
		;
connectAttr "boid240.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[105].dependNode"
		;
connectAttr "boidShape163.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[106].dependNode"
		;
connectAttr "boidShape191.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[107].dependNode"
		;
connectAttr "boidShape364.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[108].dependNode"
		;
connectAttr "boid110.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[109].dependNode"
		;
connectAttr "boidShape339.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[110].dependNode"
		;
connectAttr "boidShape230.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[111].dependNode"
		;
connectAttr "boid59.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[112].dependNode"
		;
connectAttr "boidShape370.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[113].dependNode"
		;
connectAttr "boidShape148.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[114].dependNode"
		;
connectAttr "boid210.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[115].dependNode"
		;
connectAttr "boidShape228.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[116].dependNode"
		;
connectAttr "boid184.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[117].dependNode"
		;
connectAttr "boidShape345.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[118].dependNode"
		;
connectAttr "boid144.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[119].dependNode"
		;
connectAttr "boid258.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[120].dependNode"
		;
connectAttr "boid216.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[121].dependNode"
		;
connectAttr "boidShape369.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[122].dependNode"
		;
connectAttr "boid53.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[123].dependNode"
		;
connectAttr "boidShape202.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[124].dependNode"
		;
connectAttr "boid283.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[125].dependNode"
		;
connectAttr "boid135.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[126].dependNode"
		;
connectAttr "boidShape118.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[127].dependNode"
		;
connectAttr "boidShape344.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[128].dependNode"
		;
connectAttr "boid199.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[129].dependNode"
		;
connectAttr "boidShape283.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[130].dependNode"
		;
connectAttr "boidShape110.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[131].dependNode"
		;
connectAttr "boid274.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[132].dependNode"
		;
connectAttr "boid130.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[133].dependNode"
		;
connectAttr "boidShape55.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[134].dependNode"
		;
connectAttr "boid230.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[135].dependNode"
		;
connectAttr "boid126.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[136].dependNode"
		;
connectAttr "boid209.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[137].dependNode"
		;
connectAttr "boid303.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[138].dependNode"
		;
connectAttr "boidShape249.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[139].dependNode"
		;
connectAttr "boidShape284.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[140].dependNode"
		;
connectAttr "boidShape3.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[141].dependNode"
		;
connectAttr "boidShape61.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[142].dependNode"
		;
connectAttr "boid272.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[143].dependNode"
		;
connectAttr "boid9.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[144].dependNode"
		;
connectAttr "boid284.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[145].dependNode"
		;
connectAttr "boidShape255.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[146].dependNode"
		;
connectAttr "boid297.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[147].dependNode"
		;
connectAttr "boid175.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[148].dependNode"
		;
connectAttr "boidShape43.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[149].dependNode"
		;
connectAttr "boid0.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[150].dependNode"
		;
connectAttr "boid34.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[151].dependNode"
		;
connectAttr "boid169.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[152].dependNode"
		;
connectAttr "boid44.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[153].dependNode"
		;
connectAttr "boid186.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[154].dependNode"
		;
connectAttr "boidShape327.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[155].dependNode"
		;
connectAttr "boid381.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[156].dependNode"
		;
connectAttr "boid352.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[157].dependNode"
		;
connectAttr "boidShape213.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[158].dependNode"
		;
connectAttr "boidShape186.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[159].dependNode"
		;
connectAttr "boid58.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[160].dependNode"
		;
connectAttr "boid375.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[161].dependNode"
		;
connectAttr "boidShape269.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[162].dependNode"
		;
connectAttr "boid346.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[163].dependNode"
		;
connectAttr "boidShape125.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[164].dependNode"
		;
connectAttr "boidShape322.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[165].dependNode"
		;
connectAttr "boidShape131.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[166].dependNode"
		;
connectAttr "boidShape147.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[167].dependNode"
		;
connectAttr "boid223.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[168].dependNode"
		;
connectAttr "boid195.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[169].dependNode"
		;
connectAttr "boid380.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[170].dependNode"
		;
connectAttr "boid351.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[171].dependNode"
		;
connectAttr "boid266.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[172].dependNode"
		;
connectAttr "boidShape276.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[173].dependNode"
		;
connectAttr "boidShape88.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[174].dependNode"
		;
connectAttr "boid202.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[175].dependNode"
		;
connectAttr "boid265.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[176].dependNode"
		;
connectAttr "boidShape153.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[177].dependNode"
		;
connectAttr "boidShape386.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[178].dependNode"
		;
connectAttr "boidShape41.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[179].dependNode"
		;
connectAttr "boidShape294.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[180].dependNode"
		;
connectAttr "boid290.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[181].dependNode"
		;
connectAttr "boidShape95.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[182].dependNode"
		;
connectAttr "boidShape20.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[183].dependNode"
		;
connectAttr "boid319.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[184].dependNode"
		;
connectAttr "boidShape120.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[185].dependNode"
		;
connectAttr "boidShape152.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[186].dependNode"
		;
connectAttr "boid366.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[187].dependNode"
		;
connectAttr "boidShape311.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[188].dependNode"
		;
connectAttr "boid300.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[189].dependNode"
		;
connectAttr "boidShape210.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[190].dependNode"
		;
connectAttr "boid237.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[191].dependNode"
		;
connectAttr "boid398.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[192].dependNode"
		;
connectAttr "boid111.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[193].dependNode"
		;
connectAttr "boidShape383.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[194].dependNode"
		;
connectAttr "boidShape397.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[195].dependNode"
		;
connectAttr "boid337.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[196].dependNode"
		;
connectAttr "boidShape99.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[197].dependNode"
		;
connectAttr "boid360.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[198].dependNode"
		;
connectAttr "boidShape379.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[199].dependNode"
		;
connectAttr "boidShape232.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[200].dependNode"
		;
connectAttr "boidShape206.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[201].dependNode"
		;
connectAttr "boid331.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[202].dependNode"
		;
connectAttr "boidShape354.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[203].dependNode"
		;
connectAttr "boidShape45.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[204].dependNode"
		;
connectAttr "boidShape246.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[205].dependNode"
		;
connectAttr "boid255.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[206].dependNode"
		;
connectAttr "boid176.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[207].dependNode"
		;
connectAttr "boidShape92.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[208].dependNode"
		;
connectAttr "boid250.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[209].dependNode"
		;
connectAttr "boidShape291.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[210].dependNode"
		;
connectAttr "boid275.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[211].dependNode"
		;
connectAttr "boid45.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[212].dependNode"
		;
connectAttr "boid308.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[213].dependNode"
		;
connectAttr "boid95.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[214].dependNode"
		;
connectAttr "boid162.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[215].dependNode"
		;
connectAttr "boidShape26.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[216].dependNode"
		;
connectAttr "boidShape298.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[217].dependNode"
		;
connectAttr "boidShape6.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[218].dependNode"
		;
connectAttr "boidShape317.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[219].dependNode"
		;
connectAttr "boid285.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[220].dependNode"
		;
connectAttr "boid118.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[221].dependNode"
		;
connectAttr "boid222.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[222].dependNode"
		;
connectAttr "boid201.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[223].dependNode"
		;
connectAttr "boidShape396.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[224].dependNode"
		;
connectAttr "boid205.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[225].dependNode"
		;
connectAttr "boid315.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[226].dependNode"
		;
connectAttr "boid268.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[227].dependNode"
		;
connectAttr "boid158.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[228].dependNode"
		;
connectAttr "boidShape253.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[229].dependNode"
		;
connectAttr "boidShape7.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[230].dependNode"
		;
connectAttr "boidShape49.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[231].dependNode"
		;
connectAttr "boidShape260.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[232].dependNode"
		;
connectAttr "boid309.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[233].dependNode"
		;
connectAttr "boid171.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[234].dependNode"
		;
connectAttr "blinn1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[235].dependNode"
		;
connectAttr "boidShape86.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[236].dependNode"
		;
connectAttr "boid125.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[237].dependNode"
		;
connectAttr "boid25.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[238].dependNode"
		;
connectAttr "boid29.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[239].dependNode"
		;
connectAttr "boid386.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[240].dependNode"
		;
connectAttr "boid357.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[241].dependNode"
		;
connectAttr "boid89.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[242].dependNode"
		;
connectAttr "boid172.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[243].dependNode"
		;
connectAttr "boid377.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[244].dependNode"
		;
connectAttr "boid264.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[245].dependNode"
		;
connectAttr "boidShape11.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[246].dependNode"
		;
connectAttr "boidShape216.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[247].dependNode"
		;
connectAttr "boidShape171.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[248].dependNode"
		;
connectAttr "boid185.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[249].dependNode"
		;
connectAttr "boidShape119.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[250].dependNode"
		;
connectAttr "boid348.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[252].dependNode"
		;
connectAttr "boidShape177.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[253].dependNode"
		;
connectAttr "boid41.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[254].dependNode"
		;
connectAttr "boidShape190.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[255].dependNode"
		;
connectAttr "boidShape117.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[256].dependNode"
		;
connectAttr "boid54.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[257].dependNode"
		;
connectAttr "boid115.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[258].dependNode"
		;
connectAttr "boid75.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[259].dependNode"
		;
connectAttr "boidShape56.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[260].dependNode"
		;
connectAttr "boidShape72.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[261].dependNode"
		;
connectAttr "boidShape250.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[262].dependNode"
		;
connectAttr "boidShape62.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[263].dependNode"
		;
connectAttr "boidShape134.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[264].dependNode"
		;
connectAttr "boidShape285.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[265].dependNode"
		;
connectAttr "boidShape257.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[266].dependNode"
		;
connectAttr "boidShape227.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[267].dependNode"
		;
connectAttr "boid363.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[268].dependNode"
		;
connectAttr "boid106.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[269].dependNode"
		;
connectAttr "boidShape194.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[270].dependNode"
		;
connectAttr "boidShape237.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[271].dependNode"
		;
connectAttr "boid127.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[272].dependNode"
		;
connectAttr "boid191.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[273].dependNode"
		;
connectAttr "boidShape256.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[274].dependNode"
		;
connectAttr "boid376.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[275].dependNode"
		;
connectAttr "boid147.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[276].dependNode"
		;
connectAttr "boid198.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[277].dependNode"
		;
connectAttr "boidShape44.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[278].dependNode"
		;
connectAttr "boid261.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[279].dependNode"
		;
connectAttr "boid334.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[280].dependNode"
		;
connectAttr "boidShape69.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[281].dependNode"
		;
connectAttr "boidShape76.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[282].dependNode"
		;
connectAttr "boid68.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[283].dependNode"
		;
connectAttr "boid347.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[284].dependNode"
		;
connectAttr "boidShape67.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[285].dependNode"
		;
connectAttr "boid113.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[286].dependNode"
		;
connectAttr "boidShape282.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[287].dependNode"
		;
connectAttr "boid74.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[288].dependNode"
		;
connectAttr "boidShape296.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[289].dependNode"
		;
connectAttr "boid157.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[290].dependNode"
		;
connectAttr "boid362.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[291].dependNode"
		;
connectAttr "boid133.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[292].dependNode"
		;
connectAttr "boidShape75.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[293].dependNode"
		;
connectAttr "boid312.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[294].dependNode"
		;
connectAttr "boidShape362.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[295].dependNode"
		;
connectAttr "boid324.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[296].dependNode"
		;
connectAttr "boid212.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[297].dependNode"
		;
connectAttr "boidShape214.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[298].dependNode"
		;
connectAttr "boidShape337.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[299].dependNode"
		;
connectAttr "boid333.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[300].dependNode"
		;
connectAttr "boidShape187.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[301].dependNode"
		;
connectAttr "boid28.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[302].dependNode"
		;
connectAttr "boid122.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[303].dependNode"
		;
connectAttr "boidShape103.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[304].dependNode"
		;
connectAttr "boid178.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[305].dependNode"
		;
connectAttr "boid156.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[306].dependNode"
		;
connectAttr "boid227.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[307].dependNode"
		;
connectAttr "boidShape160.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[308].dependNode"
		;
connectAttr "boidShape101.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[309].dependNode"
		;
connectAttr "boid251.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[310].dependNode"
		;
connectAttr "boidShape200.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[311].dependNode"
		;
connectAttr "boidShape107.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[312].dependNode"
		;
connectAttr "boid47.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[313].dependNode"
		;
connectAttr "boid132.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[314].dependNode"
		;
connectAttr "boid246.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[315].dependNode"
		;
connectAttr "boidShape277.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[316].dependNode"
		;
connectAttr "boid287.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[317].dependNode"
		;
connectAttr "boid57.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[318].dependNode"
		;
connectAttr "boid120.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[319].dependNode"
		;
connectAttr "boid369.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[320].dependNode"
		;
connectAttr "boidShape295.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[321].dependNode"
		;
connectAttr "boid241.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[322].dependNode"
		;
connectAttr "boidShape106.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[323].dependNode"
		;
connectAttr "boidShape267.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[324].dependNode"
		;
connectAttr "boid91.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[325].dependNode"
		;
connectAttr "boid278.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[326].dependNode"
		;
connectAttr "boidShape239.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[327].dependNode"
		;
connectAttr "boid20.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[328].dependNode"
		;
connectAttr "boid340.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[329].dependNode"
		;
connectAttr "boid236.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[330].dependNode"
		;
connectAttr "boid391.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[331].dependNode"
		;
connectAttr "boid197.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[332].dependNode"
		;
connectAttr "boidShape302.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[333].dependNode"
		;
connectAttr "boid307.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[334].dependNode"
		;
connectAttr "boidShape22.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[335].dependNode"
		;
connectAttr "boidShape321.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[336].dependNode"
		;
connectAttr "boidShape384.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[337].dependNode"
		;
connectAttr "boidShape319.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[338].dependNode"
		;
connectAttr "boid163.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[339].dependNode"
		;
connectAttr "boid301.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[340].dependNode"
		;
connectAttr "boidShape380.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[341].dependNode"
		;
connectAttr "boidShape306.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[342].dependNode"
		;
connectAttr "boidShape46.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[343].dependNode"
		;
connectAttr "boid108.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[344].dependNode"
		;
connectAttr "boidShape355.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[345].dependNode"
		;
connectAttr "boid173.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[346].dependNode"
		;
connectAttr "boidShape19.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[347].dependNode"
		;
connectAttr "boid149.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[348].dependNode"
		;
connectAttr "boid32.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[349].dependNode"
		;
connectAttr "sceneConfigurationScriptNode.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[350].dependNode"
		;
connectAttr "boid42.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[351].dependNode"
		;
connectAttr "boidShape34.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[352].dependNode"
		;
connectAttr "boid226.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[353].dependNode"
		;
connectAttr "boid76.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[354].dependNode"
		;
connectAttr "boid379.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[355].dependNode"
		;
connectAttr "boidShape8.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[356].dependNode"
		;
connectAttr "boid5.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[357].dependNode"
		;
connectAttr "boid314.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[358].dependNode"
		;
connectAttr "boidShape145.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[359].dependNode"
		;
connectAttr "boid107.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[360].dependNode"
		;
connectAttr "boidShape137.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[361].dependNode"
		;
connectAttr "boid267.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[362].dependNode"
		;
connectAttr "boidShape299.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[363].dependNode"
		;
connectAttr "boidShape33.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[364].dependNode"
		;
connectAttr "boid350.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[365].dependNode"
		;
connectAttr "boidShape245.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[366].dependNode"
		;
connectAttr "boidShape305.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[367].dependNode"
		;
connectAttr "boidShape286.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[368].dependNode"
		;
connectAttr "boid14.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[369].dependNode"
		;
connectAttr "boid124.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[370].dependNode"
		;
connectAttr "boid30.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[371].dependNode"
		;
connectAttr "boidShape12.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[372].dependNode"
		;
connectAttr "boid139.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[373].dependNode"
		;
connectAttr "boid90.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[374].dependNode"
		;
connectAttr "boidShape37.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[375].dependNode"
		;
connectAttr "boidShape290.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[376].dependNode"
		;
connectAttr "boidShape85.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[377].dependNode"
		;
connectAttr "boid60.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[378].dependNode"
		;
connectAttr "boid327.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[379].dependNode"
		;
connectAttr "boid294.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[380].dependNode"
		;
connectAttr "boid134.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[381].dependNode"
		;
connectAttr "boidShape83.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[382].dependNode"
		;
connectAttr "boid105.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[383].dependNode"
		;
connectAttr "boidShape197.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[384].dependNode"
		;
connectAttr "boid213.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[385].dependNode"
		;
connectAttr "boidShape105.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[386].dependNode"
		;
connectAttr "boid322.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[387].dependNode"
		;
connectAttr "boid288.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[388].dependNode"
		;
connectAttr "boidShape195.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[389].dependNode"
		;
connectAttr "boidShape395.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[390].dependNode"
		;
connectAttr "boidShape238.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[391].dependNode"
		;
connectAttr "boidShape111.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[392].dependNode"
		;
connectAttr "boid63.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[393].dependNode"
		;
connectAttr "boidShape215.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[394].dependNode"
		;
connectAttr "boid23.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[395].dependNode"
		;
connectAttr "boid204.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[396].dependNode"
		;
connectAttr "boidShape229.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[397].dependNode"
		;
connectAttr "boidShape375.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[398].dependNode"
		;
connectAttr "boid364.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[399].dependNode"
		;
connectAttr "boidShape142.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[400].dependNode"
		;
connectAttr "boid148.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[401].dependNode"
		;
connectAttr "boid252.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[402].dependNode"
		;
connectAttr "boidShape350.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[403].dependNode"
		;
connectAttr "boid219.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[404].dependNode"
		;
connectAttr "boidShape78.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[405].dependNode"
		;
connectAttr "boidShape242.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[406].dependNode"
		;
connectAttr "boid262.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[407].dependNode"
		;
connectAttr "boid335.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[408].dependNode"
		;
connectAttr "boidShape219.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[409].dependNode"
		;
connectAttr "boidShape271.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[410].dependNode"
		;
connectAttr "boidShape251.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[411].dependNode"
		;
connectAttr "boidShape116.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[412].dependNode"
		;
connectAttr "BOIDS.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[413].dependNode"
		;
connectAttr "boid180.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[414].dependNode"
		;
connectAttr "boid385.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[415].dependNode"
		;
connectAttr "boid356.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[416].dependNode"
		;
connectAttr "boid229.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[417].dependNode"
		;
connectAttr "boid39.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[418].dependNode"
		;
connectAttr "boid311.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[419].dependNode"
		;
connectAttr "boidShape211.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[420].dependNode"
		;
connectAttr "boid292.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[421].dependNode"
		;
connectAttr "boidShape102.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[422].dependNode"
		;
connectAttr "boidShape225.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[423].dependNode"
		;
connectAttr "boidShape66.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[424].dependNode"
		;
connectAttr "boid390.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[425].dependNode"
		;
connectAttr "boid103.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[426].dependNode"
		;
connectAttr "boid208.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[427].dependNode"
		;
connectAttr "boid121.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[428].dependNode"
		;
connectAttr "boidShape308.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[429].dependNode"
		;
connectAttr "boidShape74.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[430].dependNode"
		;
connectAttr "boid256.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[431].dependNode"
		;
connectAttr "boidShape247.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[432].dependNode"
		;
connectAttr "boid61.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[433].dependNode"
		;
connectAttr "boidShape51.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[434].dependNode"
		;
connectAttr "boidShape314.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[435].dependNode"
		;
connectAttr "boid203.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[436].dependNode"
		;
connectAttr "boidShape262.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[437].dependNode"
		;
connectAttr "boidShape281.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[438].dependNode"
		;
connectAttr "boidShape30.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[439].dependNode"
		;
connectAttr "boid3.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[440].dependNode"
		;
connectAttr "boidShape57.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[441].dependNode"
		;
connectAttr "boidShape312.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[442].dependNode"
		;
connectAttr "boidShape268.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[443].dependNode"
		;
connectAttr "boidShape28.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[444].dependNode"
		;
connectAttr "boidShape165.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[445].dependNode"
		;
connectAttr "boid128.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[446].dependNode"
		;
connectAttr "boidShape266.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[447].dependNode"
		;
connectAttr "boidShape39.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[448].dependNode"
		;
connectAttr "boid56.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[449].dependNode"
		;
connectAttr "boidShape180.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[450].dependNode"
		;
connectAttr "boid217.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[451].dependNode"
		;
connectAttr "boid383.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[452].dependNode"
		;
connectAttr "boid354.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[453].dependNode"
		;
connectAttr "boidShape385.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[454].dependNode"
		;
connectAttr "boidShape325.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[455].dependNode"
		;
connectAttr "boid87.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[456].dependNode"
		;
connectAttr "boidShape224.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[457].dependNode"
		;
connectAttr "boid378.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[458].dependNode"
		;
connectAttr "boid277.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[459].dependNode"
		;
connectAttr "boidShape179.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[460].dependNode"
		;
connectAttr "boidShape389.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[461].dependNode"
		;
connectAttr "boid81.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[462].dependNode"
		;
connectAttr "boidShape254.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[463].dependNode"
		;
connectAttr "boid349.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[464].dependNode"
		;
connectAttr "boidShape209.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[465].dependNode"
		;
connectAttr "boidShape231.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[466].dependNode"
		;
connectAttr "boidShape371.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[467].dependNode"
		;
connectAttr "boidShape198.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[468].dependNode"
		;
connectAttr "boid177.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[469].dependNode"
		;
connectAttr "boidShape94.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[470].dependNode"
		;
connectAttr "boidShape64.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[471].dependNode"
		;
connectAttr "boidShape346.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[472].dependNode"
		;
connectAttr "boidShape123.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[473].dependNode"
		;
connectAttr "boidShape301.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[474].dependNode"
		;
connectAttr "boidShape293.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[475].dependNode"
		;
connectAttr "boidShape80.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[476].dependNode"
		;
connectAttr "boid35.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[477].dependNode"
		;
connectAttr "boidShape265.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[478].dependNode"
		;
connectAttr "boid326.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[479].dependNode"
		;
connectAttr "boid46.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[480].dependNode"
		;
connectAttr "boidShape318.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[481].dependNode"
		;
connectAttr "boidShape272.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[482].dependNode"
		;
connectAttr "boid119.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[483].dependNode"
		;
connectAttr "boidShape149.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[484].dependNode"
		;
connectAttr "boidShape382.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[485].dependNode"
		;
connectAttr "boid368.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[486].dependNode"
		;
connectAttr "boid388.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[487].dependNode"
		;
connectAttr "boidShape13.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[488].dependNode"
		;
connectAttr "boid367.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[489].dependNode"
		;
connectAttr "boid253.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[490].dependNode"
		;
connectAttr "boid295.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[491].dependNode"
		;
connectAttr "boidShape91.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[492].dependNode"
		;
connectAttr "boid72.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[493].dependNode"
		;
connectAttr "boidShape304.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[494].dependNode"
		;
connectAttr "boidShape4.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[495].dependNode"
		;
connectAttr "boid193.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[496].dependNode"
		;
connectAttr "boid339.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[497].dependNode"
		;
connectAttr "boidShape309.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[498].dependNode"
		;
connectAttr "boid200.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[499].dependNode"
		;
connectAttr "boid338.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[500].dependNode"
		;
connectAttr "boid263.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[501].dependNode"
		;
connectAttr "boidShape203.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[502].dependNode"
		;
connectAttr "boidShape222.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[503].dependNode"
		;
connectAttr "boidShape17.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[504].dependNode"
		;
connectAttr "boidShape368.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[505].dependNode"
		;
connectAttr "boid10.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[506].dependNode"
		;
connectAttr "boid304.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[507].dependNode"
		;
connectAttr "boidShape377.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[508].dependNode"
		;
connectAttr "boidShape204.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[509].dependNode"
		;
connectAttr "boid243.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[510].dependNode"
		;
connectAttr "boidShape343.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[511].dependNode"
		;
connectAttr "boid317.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[512].dependNode"
		;
connectAttr "boidShape136.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[513].dependNode"
		;
connectAttr "boidShape352.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[514].dependNode"
		;
connectAttr "boidShape109.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[515].dependNode"
		;
connectAttr "boidShape244.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[516].dependNode"
		;
connectAttr "boid393.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[517].dependNode"
		;
connectAttr "boid249.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[518].dependNode"
		;
connectAttr "polyCube1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[519].dependNode"
		;
connectAttr "boid170.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[520].dependNode"
		;
connectAttr "boidShape381.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[521].dependNode"
		;
connectAttr "boidShape143.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[522].dependNode"
		;
connectAttr "boidShape356.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[523].dependNode"
		;
connectAttr "boid190.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[524].dependNode"
		;
connectAttr "boid97.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[525].dependNode"
		;
connectAttr "boidShape324.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[526].dependNode"
		;
connectAttr "boidShape243.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[527].dependNode"
		;
connectAttr "boidShape316.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[528].dependNode"
		;
connectAttr "boid100.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[529].dependNode"
		;
connectAttr "boidShape10.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[530].dependNode"
		;
connectAttr "boidShape278.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[531].dependNode"
		;
connectAttr "boidShape270.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[532].dependNode"
		;
connectAttr "boid19.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[533].dependNode"
		;
connectAttr "boidShape208.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[534].dependNode"
		;
connectAttr "boidShape323.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[535].dependNode"
		;
connectAttr "boid233.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[536].dependNode"
		;
connectAttr "mPyNode1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[537].dependNode"
		;
connectAttr "boid361.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[538].dependNode"
		;
connectAttr "boid248.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[539].dependNode"
		;
connectAttr "boid392.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[540].dependNode"
		;
connectAttr "boidShape0.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[541].dependNode"
		;
connectAttr "boidShape329.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[542].dependNode"
		;
connectAttr "boidShape374.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[543].dependNode"
		;
connectAttr "boidShape122.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[544].dependNode"
		;
connectAttr "boidShape154.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[545].dependNode"
		;
connectAttr "boid332.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[546].dependNode"
		;
connectAttr "boid228.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[547].dependNode"
		;
connectAttr "boid114.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[548].dependNode"
		;
connectAttr "boidShape349.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[549].dependNode"
		;
connectAttr "boid160.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[550].dependNode"
		;
connectAttr "boidShape48.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[551].dependNode"
		;
connectAttr "boidShape393.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[552].dependNode"
		;
connectAttr "boid155.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[553].dependNode"
		;
connectAttr "boid395.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[554].dependNode"
		;
connectAttr "boidShape96.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[555].dependNode"
		;
connectAttr "boidShape115.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[556].dependNode"
		;
connectAttr "boidShape54.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[557].dependNode"
		;
connectAttr "boidShape173.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[558].dependNode"
		;
connectAttr "boid269.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[559].dependNode"
		;
connectAttr "boid88.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[560].dependNode"
		;
connectAttr "boidShape121.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[561].dependNode"
		;
connectAttr "boidShape140.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[562].dependNode"
		;
connectAttr "boid310.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[563].dependNode"
		;
connectAttr "boidShape52.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[564].dependNode"
		;
connectAttr "boidShape127.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[565].dependNode"
		;
connectAttr "boidShape36.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[566].dependNode"
		;
connectAttr "boid82.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[567].dependNode"
		;
connectAttr "boidShape100.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[568].dependNode"
		;
connectAttr "boidShape217.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[569].dependNode"
		;
connectAttr "boid67.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[570].dependNode"
		;
connectAttr "boidShape58.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[571].dependNode"
		;
connectAttr "boidShape303.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[572].dependNode"
		;
connectAttr "boidShape42.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[573].dependNode"
		;
connectAttr "boid26.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[574].dependNode"
		;
connectAttr "boid141.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[575].dependNode"
		;
connectAttr "boidShape275.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[576].dependNode"
		;
connectAttr "boidShape233.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[577].dependNode"
		;
connectAttr "boid112.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[578].dependNode"
		;
connectAttr "boidShape40.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[579].dependNode"
		;
connectAttr "boid329.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[580].dependNode"
		;
connectAttr "boidShape16.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[581].dependNode"
		;
connectAttr "boid36.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[582].dependNode"
		;
connectAttr "boid323.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[583].dependNode"
		;
connectAttr "boid146.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[584].dependNode"
		;
connectAttr "boidShape151.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[585].dependNode"
		;
connectAttr "boid218.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[586].dependNode"
		;
connectAttr "boidShape398.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[587].dependNode"
		;
connectAttr "boid99.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[588].dependNode"
		;
connectAttr "boid206.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[589].dependNode"
		;
connectAttr "boidShape358.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[590].dependNode"
		;
connectAttr "boidShape157.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[591].dependNode"
		;
connectAttr "boid55.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[592].dependNode"
		;
connectAttr "boid140.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[593].dependNode"
		;
connectAttr "boidShape333.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[594].dependNode"
		;
connectAttr "boid254.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[595].dependNode"
		;
connectAttr "boidShape27.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[596].dependNode"
		;
connectAttr "boid183.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[597].dependNode"
		;
connectAttr "boidShape357.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[598].dependNode"
		;
connectAttr "boid102.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[599].dependNode"
		;
connectAttr "boid359.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[600].dependNode"
		;
connectAttr "boidShape113.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[601].dependNode"
		;
connectAttr "boid69.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[602].dependNode"
		;
connectAttr "boid211.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[603].dependNode"
		;
connectAttr "boidShape332.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[604].dependNode"
		;
connectAttr "boid11.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[605].dependNode"
		;
connectAttr "boid286.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[606].dependNode"
		;
connectAttr "boid330.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[607].dependNode"
		;
connectAttr "boid399.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[608].dependNode"
		;
connectAttr "boid64.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[609].dependNode"
		;
connectAttr "boidShape2.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[610].dependNode"
		;
connectAttr "boid52.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[611].dependNode"
		;
connectAttr "boid225.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[612].dependNode"
		;
connectAttr "boidShape82.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[613].dependNode"
		;
connectAttr "boid242.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[614].dependNode"
		;
connectAttr "boidShape32.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[615].dependNode"
		;
connectAttr "boid62.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[616].dependNode"
		;
connectAttr "boidShape59.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[617].dependNode"
		;
connectAttr "boidShape388.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[618].dependNode"
		;
connectAttr "boid313.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[619].dependNode"
		;
connectAttr "boidShape328.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[620].dependNode"
		;
connectAttr "boidShape169.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[621].dependNode"
		;
connectAttr "boid279.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[622].dependNode"
		;
connectAttr "boid49.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[623].dependNode"
		;
connectAttr "blinn1SG.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[624].dependNode"
		;
connectAttr "boidShape288.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[625].dependNode"
		;
connectAttr "boidShape89.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[626].dependNode"
		;
connectAttr "boidShape167.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[627].dependNode"
		;
connectAttr "boid13.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[628].dependNode"
		;
connectAttr "boid83.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[629].dependNode"
		;
connectAttr "boid166.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[630].dependNode"
		;
connectAttr "boid123.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[631].dependNode"
		;
connectAttr "boid12.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[632].dependNode"
		;
connectAttr "boidShape392.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[633].dependNode"
		;
connectAttr "boid179.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[634].dependNode"
		;
connectAttr "boid273.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[635].dependNode"
		;
connectAttr "boidShape182.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[636].dependNode"
		;
connectAttr "boidShape201.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[637].dependNode"
		;
connectAttr "boidShape212.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[638].dependNode"
		;
connectAttr "boid371.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[639].dependNode"
		;
connectAttr "boidShape23.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[640].dependNode"
		;
connectAttr "boid27.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[641].dependNode"
		;
connectAttr "boid93.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[642].dependNode"
		;
connectAttr "boid384.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[643].dependNode"
		;
connectAttr "boid355.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[644].dependNode"
		;
connectAttr "boidShape188.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[645].dependNode"
		;
connectAttr "boid342.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[646].dependNode"
		;
connectAttr "boidShape399.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[647].dependNode"
		;
connectAttr "boid37.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[648].dependNode"
		;
connectAttr "boid48.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[649].dependNode"
		;
connectAttr "boidShape126.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[650].dependNode"
		;
connectAttr "boid293.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[651].dependNode"
		;
connectAttr "boidShape158.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[652].dependNode"
		;
connectAttr "boidShape359.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[653].dependNode"
		;
connectAttr "boid109.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[654].dependNode"
		;
connectAttr "boidShape248.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[655].dependNode"
		;
connectAttr "boidShape334.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[656].dependNode"
		;
connectAttr "boidShape192.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[657].dependNode"
		;
connectAttr "boid165.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[658].dependNode"
		;
connectAttr "boid370.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[659].dependNode"
		;
connectAttr "boid79.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[660].dependNode"
		;
connectAttr "boid92.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[661].dependNode"
		;
connectAttr "boid73.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[662].dependNode"
		;
connectAttr "boid341.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[663].dependNode"
		;
connectAttr "boidShape65.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[664].dependNode"
		;
connectAttr "boid151.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[665].dependNode"
		;
connectAttr "boidShape307.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[666].dependNode"
		;
connectAttr "boidShape326.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[667].dependNode"
		;
connectAttr "boid189.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[668].dependNode"
		;
connectAttr "boidShape73.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[669].dependNode"
		;
connectAttr "boid306.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[670].dependNode"
		;
connectAttr "boidShape313.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[671].dependNode"
		;
connectAttr "boid188.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[672].dependNode"
		;
connectAttr "boid259.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[673].dependNode"
		;
connectAttr "boidShape280.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[674].dependNode"
		;
connectAttr "boidShape185.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[675].dependNode"
		;
connectAttr "boidShape87.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[676].dependNode"
		;
connectAttr "boid78.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[677].dependNode"
		;
connectAttr "boidShape390.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[678].dependNode"
		;
connectAttr "blinn2SG.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[679].dependNode"
		;
connectAttr "boid6.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[680].dependNode"
		;
connectAttr "boid137.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[681].dependNode"
		;
connectAttr "boid116.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[682].dependNode"
		;
connectAttr "boidShape21.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[683].dependNode"
		;
connectAttr "boidShape372.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[684].dependNode"
		;
connectAttr "boidShape199.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[685].dependNode"
		;
connectAttr "boid150.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[686].dependNode"
		;
connectAttr "boid328.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[687].dependNode"
		;
connectAttr "boidShape164.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[688].dependNode"
		;
connectAttr "boid131.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[689].dependNode"
		;
connectAttr "boidShape347.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[690].dependNode"
		;
connectAttr "boidShape124.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[691].dependNode"
		;
connectAttr "boid16.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[692].dependNode"
		;
connectAttr "boid245.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[693].dependNode"
		;
connectAttr "boidShape156.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[694].dependNode"
		;
connectAttr "boid232.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[695].dependNode"
		;
connectAttr "boid320.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[696].dependNode"
		;
connectAttr "boid182.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[697].dependNode"
		;
connectAttr "defaultRenderLayer.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[698].dependNode"
		;
connectAttr "boid389.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[699].dependNode"
		;
connectAttr "boidShape223.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[700].dependNode"
		;
connectAttr "boidShape98.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[701].dependNode"
		;
connectAttr "boidShape287.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[702].dependNode"
		;
connectAttr "boid299.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[703].dependNode"
		;
connectAttr "boidShape259.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[704].dependNode"
		;
connectAttr "boidShape273.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[705].dependNode"
		;
connectAttr "boid280.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[706].dependNode"
		;
connectAttr "boid51.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[707].dependNode"
		;
connectAttr "boid394.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[708].dependNode"
		;
connectAttr "boid235.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[709].dependNode"
		;
connectAttr "boid136.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[710].dependNode"
		;
connectAttr "boid2.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[711].dependNode"
		;
connectAttr "boidShape14.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[712].dependNode"
		;
connectAttr "boid15.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[713].dependNode"
		;
connectAttr "boidShape5.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[714].dependNode"
		;
connectAttr "boidShape93.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[715].dependNode"
		;
connectAttr "boidShape63.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[716].dependNode"
		;
connectAttr "boidShape258.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[717].dependNode"
		;
connectAttr "boid96.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[718].dependNode"
		;
connectAttr "boidShape310.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[719].dependNode"
		;
connectAttr "boid244.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[720].dependNode"
		;
connectAttr "boidShape172.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[721].dependNode"
		;
connectAttr "boid373.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[722].dependNode"
		;
connectAttr "boid65.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[723].dependNode"
		;
connectAttr "boidShape292.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[724].dependNode"
		;
connectAttr "boidShape264.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[725].dependNode"
		;
connectAttr "boidShape18.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[726].dependNode"
		;
connectAttr "boid40.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[727].dependNode"
		;
connectAttr "boid344.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[728].dependNode"
		;
connectAttr "boidShape378.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[729].dependNode"
		;
connectAttr "boidShape205.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[730].dependNode"
		;
connectAttr "boid221.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[731].dependNode"
		;
connectAttr "boidShape176.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[732].dependNode"
		;
connectAttr "boidShape331.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[733].dependNode"
		;
connectAttr "boidShape353.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[734].dependNode"
		;
connectAttr "boid71.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[735].dependNode"
		;
connectAttr "boid1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[736].dependNode"
		;
connectAttr "boid234.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[737].dependNode"
		;
connectAttr "boidShape25.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[738].dependNode"
		;
connectAttr "boid84.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[739].dependNode"
		;
connectAttr "boid305.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[740].dependNode"
		;
connectAttr "boid387.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[741].dependNode"
		;
connectAttr "boid167.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[742].dependNode"
		;
connectAttr "boid358.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[743].dependNode"
		;
connectAttr "boidShape363.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[744].dependNode"
		;
connectAttr "boidShape144.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[745].dependNode"
		;
connectAttr "boidShape338.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[746].dependNode"
		;
connectAttr "boid382.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[747].dependNode"
		;
connectAttr "boid353.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[748].dependNode"
		;
connectAttr "boid4.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[749].dependNode"
		;
connectAttr "boid22.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[750].dependNode"
		;
connectAttr "boidShape221.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[751].dependNode"
		;
connectAttr "boid220.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[752].dependNode"
		;
connectAttr "boid38.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[753].dependNode"
		;
connectAttr "boidShape367.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[754].dependNode"
		;
connectAttr "boidShape68.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[755].dependNode"
		;
connectAttr "boidShape129.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[756].dependNode"
		;
connectAttr "boid85.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[757].dependNode"
		;
connectAttr "boidShape279.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[758].dependNode"
		;
connectAttr "blinn2.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[759].dependNode"
		;
connectAttr "boidShape342.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[760].dependNode"
		;
connectAttr "boid98.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[761].dependNode"
		;
connectAttr "boid181.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[762].dependNode"
		;
connectAttr "boidShape297.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[763].dependNode"
		;
connectAttr "boidShape135.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[764].dependNode"
		;
connectAttr "boid101.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[765].dependNode"
		;
connectAttr "boid129.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[766].dependNode"
		;
connectAttr "boidShape108.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[767].dependNode"
		;
connectAttr "boid142.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[768].dependNode"
		;
connectAttr "boidShape330.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[769].dependNode"
		;
connectAttr "boid239.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[770].dependNode"
		;
connectAttr "boid50.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[771].dependNode"
		;
connectAttr "boidShape155.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[772].dependNode"
		;
connectAttr "boid296.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[773].dependNode"
		;
connectAttr "boidShape394.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[774].dependNode"
		;
connectAttr "boidShape161.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[775].dependNode"
		;
connectAttr "boidShape97.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[776].dependNode"
		;
connectAttr "boidShape315.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[777].dependNode"
		;
connectAttr "boidShape174.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[778].dependNode"
		;
connectAttr "boidShape9.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[779].dependNode"
		;
connectAttr "boid33.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[780].dependNode"
		;
connectAttr "boid372.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[781].dependNode"
		;
connectAttr "boid94.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[782].dependNode"
		;
connectAttr "boid257.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[783].dependNode"
		;
connectAttr "boid207.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[784].dependNode"
		;
connectAttr "boidShape207.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[785].dependNode"
		;
connectAttr "boidShape128.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[786].dependNode"
		;
connectAttr "boid215.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[787].dependNode"
		;
connectAttr "boid343.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[788].dependNode"
		;
connectAttr "boid270.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[789].dependNode"
		;
connectAttr "boid7.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[790].dependNode"
		;
connectAttr "boidShape218.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[791].dependNode"
		;
connectAttr "boid282.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[792].dependNode"
		;
connectAttr "boid117.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[793].dependNode"
		;
connectAttr "boidShape373.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[794].dependNode"
		;
connectAttr "boidShape391.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[795].dependNode"
		;
connectAttr "boid70.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[796].dependNode"
		;
connectAttr "boidShape234.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[797].dependNode"
		;
connectAttr "boidShape70.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[798].dependNode"
		;
connectAttr "boidShape132.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[799].dependNode"
		;
connectAttr "boidShape263.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[800].dependNode"
		;
connectAttr "boidShape348.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[801].dependNode"
		;
connectAttr "boidShape365.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[802].dependNode"
		;
connectAttr "boidShape47.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[803].dependNode"
		;
connectAttr "boidShape240.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[804].dependNode"
		;
connectAttr "boidShape235.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[805].dependNode"
		;
connectAttr "boid321.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[806].dependNode"
		;
connectAttr "boidShape340.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[807].dependNode"
		;
connectAttr "boidShape114.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[808].dependNode"
		;
connectAttr "boidShape53.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[809].dependNode"
		;
connectAttr "blinn1SG.partition" ":renderPartition.sets" -nextAvailable;
connectAttr "blinn2SG.partition" ":renderPartition.sets" -nextAvailable;
connectAttr "blinn1.message" ":defaultShaderList1.shaders" -nextAvailable;
connectAttr "blinn2.message" ":defaultShaderList1.shaders" -nextAvailable;
connectAttr "defaultRenderLayer.message" ":defaultRenderingList1.rendering" -nextAvailable
		;
// End of boids.ma
