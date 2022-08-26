//Maya ASCII 2022 scene
//Name: quaternionSpineNode.ma
//Last modified: Thu, Aug 25, 2022 11:26:07 AM
//Codeset: 1252
requires maya "2022";
requires -nodeType "mPyNode" "mpynode_plugin.py" "1.0";
requires "stereoCamera" "10.0";
currentUnit -linear centimeter -angle degree -time ntsc;
fileInfo "application" "maya";
fileInfo "product" "Maya 2022";
fileInfo "version" "2022";
fileInfo "cutIdentifier" "202205171752-c25c06f306";
fileInfo "osv" "Windows 10 Enterprise v2009 (Build: 19044)";
fileInfo "UUID" "A2F3308E-41BF-3C4F-E081-7D8284F0CF5A";
createNode transform -shared -name "persp";
	rename -uuid "8E259036-4AA5-9969-1B8F-78B43E775DA2";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 6.2634594025185342 10.874024714308625 27.784631958297417 ;
	setAttr ".rotate" -type "double3" -11.13835272957226 370.19999999955633 -2.0197678792873184e-16 ;
createNode camera -shared -name "perspShape" -parent "persp";
	rename -uuid "EAD1C557-4831-D914-7EA5-4DBCB06346DC";
	setAttr -keyable off ".visibility" no;
	setAttr ".focalLength" 34.999999999999993;
	setAttr ".farClipPlane" 5000;
	setAttr ".centerOfInterest" 26.422912946413494;
	setAttr ".imageName" -type "string" "persp";
	setAttr ".depthName" -type "string" "persp_depth";
	setAttr ".maskName" -type "string" "persp_mask";
	setAttr ".homeCommand" -type "string" "viewSet -p %camera";
createNode transform -shared -name "top";
	rename -uuid "E66E4897-43E5-DAB5-5D2D-0983E62D0817";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 0 1000.1 0 ;
	setAttr ".rotate" -type "double3" -89.999999999999986 0 0 ;
createNode camera -shared -name "topShape" -parent "top";
	rename -uuid "09DB9656-420D-A46E-5B81-AEB87B11665C";
	setAttr -keyable off ".visibility" no;
	setAttr ".renderable" no;
	setAttr ".farClipPlane" 5000;
	setAttr ".centerOfInterest" 1000.1;
	setAttr ".orthographicWidth" 9.8838896952104491;
	setAttr ".imageName" -type "string" "top";
	setAttr ".depthName" -type "string" "top_depth";
	setAttr ".maskName" -type "string" "top_mask";
	setAttr ".homeCommand" -type "string" "viewSet -t %camera";
	setAttr ".orthographic" yes;
createNode transform -shared -name "front";
	rename -uuid "BB342D48-4A86-B191-37D4-51A368FE807D";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" -3.5784396813453383 6.1805464607797216 1000.1 ;
createNode camera -shared -name "frontShape" -parent "front";
	rename -uuid "5FA245E2-4905-3DB5-8FC5-D3A260944FA0";
	setAttr -keyable off ".visibility" no;
	setAttr ".renderable" no;
	setAttr ".farClipPlane" 5000;
	setAttr ".centerOfInterest" 1000.1;
	setAttr ".orthographicWidth" 38.892313283673175;
	setAttr ".imageName" -type "string" "front";
	setAttr ".depthName" -type "string" "front_depth";
	setAttr ".maskName" -type "string" "front_mask";
	setAttr ".homeCommand" -type "string" "viewSet -f %camera";
	setAttr ".orthographic" yes;
createNode transform -shared -name "side";
	rename -uuid "9490F27B-4762-7309-171C-3582645A7660";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 1000.1 2.1021897810218961 -1.1824817518248154 ;
	setAttr ".rotate" -type "double3" 0 89.999999999999986 0 ;
createNode camera -shared -name "sideShape" -parent "side";
	rename -uuid "164F4EAE-4132-B7E2-D70C-30B63299AF82";
	setAttr -keyable off ".visibility" no;
	setAttr ".renderable" no;
	setAttr ".farClipPlane" 5000;
	setAttr ".centerOfInterest" 1000.1;
	setAttr ".orthographicWidth" 30;
	setAttr ".imageName" -type "string" "side";
	setAttr ".depthName" -type "string" "side_depth";
	setAttr ".maskName" -type "string" "side_mask";
	setAttr ".homeCommand" -type "string" "viewSet -s %camera";
	setAttr ".orthographic" yes;
createNode transform -name "curve1";
	rename -uuid "FA124C29-419B-A7D3-3C21-90830C32E8B6";
	addAttr -cachedInternally true -keyable true -shortName "stretch" -longName "stretch" 
		-minValue 0 -maxValue 1 -attributeType "double";
	addAttr -cachedInternally true -keyable true -shortName "pivot" -longName "pivot" 
		-attributeType "double";
	addAttr -cachedInternally true -keyable true -shortName "shift" -longName "shift" 
		-attributeType "double";
	addAttr -cachedInternally true -keyable true -shortName "Scale" -longName "Scale" 
		-defaultValue 1 -attributeType "double";
	addAttr -cachedInternally true -keyable true -shortName "resetDefaultLength" -longName "resetDefaultLength" 
		-minValue 0 -maxValue 1 -enumName "False:True" -attributeType "enum";
	addAttr -cachedInternally true -keyable true -shortName "curveInvertAimAxis" -longName "curveInvertAimAxis" 
		-minValue 0 -maxValue 1 -enumName "False:True" -attributeType "enum";
	addAttr -cachedInternally true -keyable true -shortName "curveInvertUpAxis" -longName "curveInvertUpAxis" 
		-minValue 0 -maxValue 1 -enumName "False:True" -attributeType "enum";
	addAttr -cachedInternally true -keyable true -shortName "curveAimAxis" -longName "curveAimAxis" 
		-defaultValue 1 -minValue 0 -maxValue 2 -enumName "X:Y:Z" -attributeType "enum";
	addAttr -cachedInternally true -keyable true -shortName "curveUpAxis" -longName "curveUpAxis" 
		-defaultValue 2 -minValue 0 -maxValue 2 -enumName "X:Y:Z" -attributeType "enum";
	addAttr -cachedInternally true -keyable true -shortName "scaleMethod" -longName "scaleMethod" 
		-minValue 0 -maxValue 2 -enumName "Square Root:Linear:Cosine" -attributeType "enum";
	setAttr -lock on -keyable off ".visibility";
	setAttr -lock on -keyable off ".translateX";
	setAttr -lock on -keyable off ".translateY";
	setAttr -lock on -keyable off ".translateZ";
	setAttr -lock on -keyable off ".rotateX";
	setAttr -lock on -keyable off ".rotateY";
	setAttr -lock on -keyable off ".rotateZ";
	setAttr -lock on -keyable off ".scaleX";
	setAttr -lock on -keyable off ".scaleY";
	setAttr -lock on -keyable off ".scaleZ";
	setAttr -keyable on ".stretch";
	setAttr -keyable on ".pivot";
	setAttr -keyable on ".shift";
	setAttr -keyable on ".Scale";
	setAttr -keyable on ".resetDefaultLength";
	setAttr -keyable on ".curveInvertAimAxis";
	setAttr -keyable on ".curveInvertUpAxis";
	setAttr -keyable on ".curveAimAxis";
	setAttr -keyable on ".curveUpAxis" 0;
	setAttr -keyable on ".scaleMethod";
createNode nurbsCurve -name "curveShape1" -parent "curve1";
	rename -uuid "57E59043-4330-ADAC-0706-60AF2D90F404";
	setAttr -keyable off ".visibility";
	setAttr -size 12 ".instObjGroups[0].objectGroups";
	setAttr ".tweak" yes;
createNode nurbsCurve -name "curveShape1Orig" -parent "curve1";
	rename -uuid "C19DFF21-44F8-390F-50A2-B18EE8A5D733";
	setAttr -keyable off ".visibility";
	setAttr ".intermediateObject" yes;
	setAttr ".cached" -type "nurbsCurve" 
		3 2 0 no 3
		7 0 0 0 1 2 2 2
		5
		0 0 0
		0 3 0
		0 6 0
		0 9 0
		0 12 0
		;
createNode transform -name "group1";
	rename -uuid "A1625C26-4A4E-51AF-7ECB-FBA77D9E87F9";
createNode transform -name "locator1" -parent "group1";
	rename -uuid "A7FD6558-4219-809E-69B1-4EAF96FB769F";
createNode locator -name "locatorShape1" -parent "locator1";
	rename -uuid "D8619E8C-46AE-053A-2B96-3290B4A4EF56";
	setAttr -keyable off ".visibility";
	setAttr ".localScale" -type "double3" 2 2 2 ;
createNode transform -name "cluster1Handle" -parent "locator1";
	rename -uuid "07310B2D-461B-04A8-0432-7B8460CD668D";
	setAttr ".visibility" no;
createNode clusterHandle -name "cluster1HandleShape" -parent "cluster1Handle";
	rename -uuid "ADD49ECC-42C3-C94B-0232-A88795F89A6B";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr -keyable off ".visibility";
createNode transform -name "locator2" -parent "group1";
	rename -uuid "081772C1-4CB0-B893-06B2-25AAB8D51FBB";
createNode locator -name "locatorShape2" -parent "locator2";
	rename -uuid "F04B59AC-4F84-2DAA-0C71-3D91DB6DAAC9";
	setAttr -keyable off ".visibility";
	setAttr ".localScale" -type "double3" 2 2 2 ;
createNode transform -name "cluster2Handle" -parent "locator2";
	rename -uuid "6124FB0F-4A07-0C3A-FB9F-EA99485DBEF1";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 0 -3 0 ;
	setAttr ".rotatePivot" -type "double3" 0 3 0 ;
	setAttr ".scalePivot" -type "double3" 0 3 0 ;
createNode clusterHandle -name "cluster2HandleShape" -parent "cluster2Handle";
	rename -uuid "02E0AAED-4215-D70E-EF53-2F838B0742A9";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr -keyable off ".visibility";
	setAttr ".origin" -type "double3" 0 3 0 ;
createNode transform -name "locator3" -parent "group1";
	rename -uuid "BACD9C42-4193-ADF2-EC92-F48FF7338A1A";
createNode locator -name "locatorShape3" -parent "locator3";
	rename -uuid "77566323-44E9-E04D-E0FE-F4919BBFF0C3";
	setAttr -keyable off ".visibility";
	setAttr ".localScale" -type "double3" 2 2 2 ;
createNode transform -name "cluster3Handle" -parent "locator3";
	rename -uuid "560B1AE9-497C-EA3B-68EE-5D811C502B58";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 0 -6 0 ;
	setAttr ".rotatePivot" -type "double3" 0 6 0 ;
	setAttr ".scalePivot" -type "double3" 0 6 0 ;
createNode clusterHandle -name "cluster3HandleShape" -parent "cluster3Handle";
	rename -uuid "07B581BF-44C3-2AB1-4E7D-9C9DEA3887EE";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr -keyable off ".visibility";
	setAttr ".origin" -type "double3" 0 6 0 ;
createNode transform -name "locator4" -parent "group1";
	rename -uuid "01BB336D-4ED1-FC12-767B-EDA46C8F4916";
createNode locator -name "locatorShape4" -parent "locator4";
	rename -uuid "72F58B8E-4DF3-4C75-908A-C5B7CC722ACB";
	setAttr -keyable off ".visibility";
	setAttr ".localScale" -type "double3" 2 2 2 ;
createNode transform -name "cluster4Handle" -parent "locator4";
	rename -uuid "8A3E37F8-4EE7-1A9D-C098-6EA16DD54FB3";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 0 -9 0 ;
	setAttr ".rotatePivot" -type "double3" 0 9 0 ;
	setAttr ".scalePivot" -type "double3" 0 9 0 ;
createNode clusterHandle -name "cluster4HandleShape" -parent "cluster4Handle";
	rename -uuid "67B52132-41AB-5CFA-1D9F-9EBABF91E72A";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr -keyable off ".visibility";
	setAttr ".origin" -type "double3" 0 9 0 ;
createNode transform -name "locator5" -parent "group1";
	rename -uuid "6C4C2192-4362-A711-8280-2F93F9BC1C6E";
createNode locator -name "locatorShape5" -parent "locator5";
	rename -uuid "6B82D837-4454-79F1-B312-C29EE7897E8D";
	setAttr -keyable off ".visibility";
	setAttr ".localScale" -type "double3" 2 2 2 ;
createNode transform -name "cluster5Handle" -parent "locator5";
	rename -uuid "95755CF5-4ED6-B215-5462-B08C658F721A";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 0 -12 0 ;
	setAttr ".rotatePivot" -type "double3" 0 12 0 ;
	setAttr ".scalePivot" -type "double3" 0 12 0 ;
createNode clusterHandle -name "cluster5HandleShape" -parent "cluster5Handle";
	rename -uuid "7D9AB130-4E1F-8AB1-C7AF-029E73540CBF";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr -keyable off ".visibility";
	setAttr ".origin" -type "double3" 0 12 0 ;
createNode transform -name "group2";
	rename -uuid "3D77EC16-4C05-F437-F0D8-E3B4E18CEDEC";
createNode transform -name "pCube1" -parent "group2";
	rename -uuid "3651A5EF-4B28-5E3B-0BAB-D181C4493269";
	addAttr -cachedInternally true -shortName "u" -longName "u" -attributeType "double";
	setAttr ".displayLocalAxis" yes;
	setAttr -keyable on ".u";
createNode mesh -name "pCubeShape1" -parent "pCube1";
	rename -uuid "730F03D5-454E-FD27-1EA7-25834F522634";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr ".tangentSpace" 1;
createNode transform -name "pCube2" -parent "group2";
	rename -uuid "C6C3AE27-45F4-7408-142F-1FA90B7DC31F";
	addAttr -cachedInternally true -shortName "u" -longName "u" -attributeType "double";
	setAttr ".displayLocalAxis" yes;
	setAttr -keyable on ".u";
createNode mesh -name "pCubeShape2" -parent "pCube2";
	rename -uuid "97DF9DD6-4DF7-3545-58AA-0CABD1EE29A8";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tangentSpace" 1;
createNode transform -name "pCube3" -parent "group2";
	rename -uuid "6BDD74FE-431C-B852-80F9-1A97A81A7989";
	addAttr -cachedInternally true -shortName "u" -longName "u" -attributeType "double";
	setAttr ".displayLocalAxis" yes;
	setAttr -keyable on ".u";
createNode mesh -name "pCubeShape3" -parent "pCube3";
	rename -uuid "1786FAEF-4DF1-75B9-48E4-759E5BBF2A37";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tangentSpace" 1;
createNode transform -name "pCube4" -parent "group2";
	rename -uuid "EFACDA95-412D-76AA-8CA1-8789819C3BFE";
	addAttr -cachedInternally true -shortName "u" -longName "u" -attributeType "double";
	setAttr ".displayLocalAxis" yes;
	setAttr -keyable on ".u";
createNode mesh -name "pCubeShape4" -parent "pCube4";
	rename -uuid "1653E180-4940-9D58-94FB-9E8C416906FD";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tangentSpace" 1;
createNode transform -name "pCube5" -parent "group2";
	rename -uuid "16DE0823-410A-8C94-8DF4-CCB3FE330C79";
	addAttr -cachedInternally true -shortName "u" -longName "u" -attributeType "double";
	setAttr ".displayLocalAxis" yes;
	setAttr -keyable on ".u";
createNode mesh -name "pCubeShape5" -parent "pCube5";
	rename -uuid "FBE0E17D-4682-E7F9-6277-B68CAE7FAA32";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tangentSpace" 1;
createNode transform -name "pCube6" -parent "group2";
	rename -uuid "E7F7D440-41F5-68E2-7FBD-D3B61AEF5703";
	addAttr -cachedInternally true -shortName "u" -longName "u" -attributeType "double";
	setAttr ".displayLocalAxis" yes;
	setAttr -keyable on ".u";
createNode mesh -name "pCubeShape6" -parent "pCube6";
	rename -uuid "300BEF71-4F3D-10DA-36CE-C291593867BE";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tangentSpace" 1;
createNode transform -name "pCube7" -parent "group2";
	rename -uuid "510F7811-498C-EACB-1E66-FEADC230E2DC";
	addAttr -cachedInternally true -shortName "u" -longName "u" -attributeType "double";
	setAttr ".displayLocalAxis" yes;
	setAttr -keyable on ".u";
createNode mesh -name "pCubeShape7" -parent "pCube7";
	rename -uuid "80FB80A3-497A-39E7-2E7A-CC92D9143A6E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tangentSpace" 1;
createNode transform -name "pCube8" -parent "group2";
	rename -uuid "65344124-4017-D918-DF3D-D0B093669458";
	addAttr -cachedInternally true -shortName "u" -longName "u" -attributeType "double";
	setAttr ".displayLocalAxis" yes;
	setAttr -keyable on ".u";
createNode mesh -name "pCubeShape8" -parent "pCube8";
	rename -uuid "809B7931-43B2-BC50-62BE-D6BB69CBAB9E";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tangentSpace" 1;
createNode transform -name "pCube9" -parent "group2";
	rename -uuid "1D28CA0B-4932-0605-42DB-B190C782D0F1";
	addAttr -cachedInternally true -shortName "u" -longName "u" -attributeType "double";
	setAttr ".displayLocalAxis" yes;
	setAttr -keyable on ".u";
createNode mesh -name "pCubeShape9" -parent "pCube9";
	rename -uuid "2FDEE6F1-4024-7007-2C64-3BB4798E5F96";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tangentSpace" 1;
createNode transform -name "pCube10" -parent "group2";
	rename -uuid "0C0A25E1-4905-7E03-A33D-F7B01D3488E8";
	addAttr -cachedInternally true -shortName "u" -longName "u" -attributeType "double";
	setAttr ".displayLocalAxis" yes;
	setAttr -keyable on ".u";
createNode mesh -name "pCubeShape10" -parent "pCube10";
	rename -uuid "65722D0C-4B5D-DAF0-9E46-DC87F336F51C";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tangentSpace" 1;
createNode transform -name "pCube11" -parent "group2";
	rename -uuid "2586CE0D-4B20-6C91-7F71-01AADEE95628";
	addAttr -cachedInternally true -shortName "u" -longName "u" -attributeType "double";
	setAttr ".displayLocalAxis" yes;
	setAttr -keyable on ".u";
createNode mesh -name "pCubeShape11" -parent "pCube11";
	rename -uuid "F0EDA641-417F-F26F-21FE-C58B46A74273";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr -size 14 ".uvSet[0].uvSetPoints[0:13]" -type "float2" 0.375
		 0 0.625 0 0.375 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1
		 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
	setAttr -size 8 ".vrts[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5
		 0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -size 12 ".edge[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0
		 2 4 0 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -size 6 -capacityHint 24 ".face[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".creaseData" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".creaseVertexData" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pinData[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".holeFaceData" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tangentSpace" 1;
createNode lightLinker -shared -name "lightLinker1";
	rename -uuid "93701B84-41B3-557A-A88F-28AF34CBECCA";
	setAttr -size 2 ".link";
	setAttr -size 2 ".shadowLink";
createNode shapeEditorManager -name "shapeEditorManager";
	rename -uuid "6168D61C-44A0-4793-A38A-A49B38CBA7D3";
createNode poseInterpolatorManager -name "poseInterpolatorManager";
	rename -uuid "4640184E-4656-E2DF-0D28-EEA669842D52";
createNode displayLayerManager -name "layerManager";
	rename -uuid "A81861E3-4F4E-CB7A-3690-50956692C4DC";
createNode displayLayer -name "defaultLayer";
	rename -uuid "CBDE64CC-4234-AB21-6BE9-4291DC6883B9";
createNode renderLayerManager -name "renderLayerManager";
	rename -uuid "B4A813F9-4DAA-90E2-93C6-73ADF4C78F34";
createNode renderLayer -name "defaultRenderLayer";
	rename -uuid "2437A304-4D80-C9B3-240D-A09911FB62E7";
	setAttr ".global" yes;
createNode cluster -name "cluster1";
	rename -uuid "F1EE99B4-44CB-77F7-8C0D-EC9F01571186";
	setAttr ".input[0].componentTagExpression" -type "string" "";
	setAttr ".geomMatrix[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".angleInterpolation" 0;
createNode tweak -name "tweak1";
	rename -uuid "A1B93EC3-4C00-716B-A3D0-95A50E44E8DD";
createNode objectSet -name "cluster1Set";
	rename -uuid "FBBBC84F-440C-1E6A-0171-3EA03872BFDA";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".verticesOnlySet" yes;
createNode groupId -name "cluster1GroupId";
	rename -uuid "C227A703-4486-EF6B-9AC8-1FA0FB50DAFC";
	setAttr ".isHistoricallyInteresting" 0;
createNode groupParts -name "cluster1GroupParts";
	rename -uuid "7D4AC451-4EBF-DF4B-0340-3A8BACC7139B";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".inputComponents" -type "componentList" 1 "cv[0]";
createNode objectSet -name "tweakSet1";
	rename -uuid "114265B4-4403-4F1F-81D4-BEAB03FB5C57";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".verticesOnlySet" yes;
createNode groupId -name "groupId2";
	rename -uuid "51C4197E-41CC-9BC8-C58B-65BA2A732C69";
	setAttr ".isHistoricallyInteresting" 0;
createNode groupParts -name "groupParts2";
	rename -uuid "0DDFD21E-4F4A-A7A6-5E90-14B8765A9C9A";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".inputComponents" -type "componentList" 1 "cv[*]";
createNode cluster -name "cluster2";
	rename -uuid "36261759-4E86-6F2D-F80A-DE8DFA96BE0F";
	setAttr ".input[0].componentTagExpression" -type "string" "";
	setAttr ".geomMatrix[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".angleInterpolation" 0;
createNode objectSet -name "cluster2Set";
	rename -uuid "713971F3-4DA1-6B07-06B5-8B8E9F803500";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".verticesOnlySet" yes;
createNode groupId -name "cluster2GroupId";
	rename -uuid "235C4134-4953-5DFE-FE75-02A4E4BF26B3";
	setAttr ".isHistoricallyInteresting" 0;
createNode groupParts -name "cluster2GroupParts";
	rename -uuid "9E096AF5-41F1-5A70-9E92-D992439B424A";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".inputComponents" -type "componentList" 1 "cv[1]";
createNode cluster -name "cluster3";
	rename -uuid "87F356CE-413B-7858-FBF4-ED9AEAFF456D";
	setAttr ".input[0].componentTagExpression" -type "string" "";
	setAttr ".geomMatrix[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".angleInterpolation" 0;
createNode objectSet -name "cluster3Set";
	rename -uuid "4161B9D5-4D90-0087-EF06-6FB7BE845F4A";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".verticesOnlySet" yes;
createNode groupId -name "cluster3GroupId";
	rename -uuid "7FBF5E68-43FF-5651-EBAE-B08134B96CA5";
	setAttr ".isHistoricallyInteresting" 0;
createNode groupParts -name "cluster3GroupParts";
	rename -uuid "2AA13D06-49C8-8469-83F0-CD9F8FFA8D1C";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".inputComponents" -type "componentList" 1 "cv[2]";
createNode cluster -name "cluster4";
	rename -uuid "279F5287-4ABA-EC2A-D4F9-98A471BF3F6B";
	setAttr ".input[0].componentTagExpression" -type "string" "";
	setAttr ".geomMatrix[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".angleInterpolation" 0;
createNode objectSet -name "cluster4Set";
	rename -uuid "42E09FAA-4B05-997F-56E4-A69CE37C76B4";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".verticesOnlySet" yes;
createNode groupId -name "cluster4GroupId";
	rename -uuid "C805E092-463C-F784-F091-B096A22372C8";
	setAttr ".isHistoricallyInteresting" 0;
createNode groupParts -name "cluster4GroupParts";
	rename -uuid "73D99EC5-4BA6-1401-0F04-3EB00F5C0B08";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".inputComponents" -type "componentList" 1 "cv[3]";
createNode cluster -name "cluster5";
	rename -uuid "2EF5FB32-4A44-D077-96F7-A09EDBAB0191";
	setAttr ".input[0].componentTagExpression" -type "string" "";
	setAttr ".geomMatrix[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".angleInterpolation" 0;
createNode objectSet -name "cluster5Set";
	rename -uuid "E4C2E547-4B85-0FD9-82A1-D88BF764F502";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".verticesOnlySet" yes;
createNode groupId -name "cluster5GroupId";
	rename -uuid "0AEE83BB-4F7A-C5AB-273A-E194BB15CB22";
	setAttr ".isHistoricallyInteresting" 0;
createNode groupParts -name "cluster5GroupParts";
	rename -uuid "A8E5C018-4474-448C-FD32-DF8FF7F82F98";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".inputComponents" -type "componentList" 1 "cv[4]";
createNode mPyNode -name "spineNode";
	rename -uuid "280D4CCF-4053-5D2C-D0DD-E1A5AFE8ACAE";
	addAttr -readable false -cachedInternally true -keyable true -shortName "inputCurve" 
		-longName "inputCurve" -dataType "nurbsCurve";
	addAttr -readable false -cachedInternally true -keyable true -multi -shortName "controlMatrices" 
		-longName "controlMatrices" -attributeType "matrix";
	addAttr -writable false -storable false -keyable true -multi -shortName "outputScale" 
		-longName "outputScale" -attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -keyable true -shortName "outputScaleX" 
		-longName "outputScaleX" -attributeType "double" -parent "outputScale";
	addAttr -writable false -storable false -keyable true -shortName "outputScaleY" 
		-longName "outputScaleY" -attributeType "double" -parent "outputScale";
	addAttr -writable false -storable false -keyable true -shortName "outputScaleZ" 
		-longName "outputScaleZ" -attributeType "double" -parent "outputScale";
	addAttr -writable false -storable false -keyable true -multi -shortName "outputRotate" 
		-longName "outputRotate" -attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -keyable true -shortName "outputRotateX" 
		-longName "outputRotateX" -attributeType "doubleAngle" -parent "outputRotate";
	addAttr -writable false -storable false -keyable true -shortName "outputRotateY" 
		-longName "outputRotateY" -attributeType "doubleAngle" -parent "outputRotate";
	addAttr -writable false -storable false -keyable true -shortName "outputRotateZ" 
		-longName "outputRotateZ" -attributeType "doubleAngle" -parent "outputRotate";
	addAttr -writable false -storable false -keyable true -multi -shortName "outputTranslate" 
		-longName "outputTranslate" -attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -keyable true -shortName "outputTranslateX" 
		-longName "outputTranslateX" -attributeType "double" -parent "outputTranslate";
	addAttr -writable false -storable false -keyable true -shortName "outputTranslateY" 
		-longName "outputTranslateY" -attributeType "double" -parent "outputTranslate";
	addAttr -writable false -storable false -keyable true -shortName "outputTranslateZ" 
		-longName "outputTranslateZ" -attributeType "double" -parent "outputTranslate";
	addAttr -readable false -cachedInternally true -keyable true -shortName "stretch" 
		-longName "stretch" -attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "pivot" 
		-longName "pivot" -attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "shift" 
		-longName "shift" -attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "scale" 
		-longName "scale" -attributeType "double";
	addAttr -readable false -cachedInternally true -multi -shortName "samples" -longName "samples" 
		-attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "resetDefaultLength" 
		-longName "resetDefaultLength" -minValue 0 -maxValue 1 -enumName "False:True" -attributeType "enum";
	addAttr -readable false -cachedInternally true -keyable true -shortName "curveInvertAimAxis" 
		-longName "curveInvertAimAxis" -minValue 0 -maxValue 1 -enumName "False:True" -attributeType "enum";
	addAttr -readable false -cachedInternally true -keyable true -shortName "curveInvertUpAxis" 
		-longName "curveInvertUpAxis" -minValue 0 -maxValue 1 -enumName "False:True" -attributeType "enum";
	addAttr -readable false -cachedInternally true -keyable true -shortName "curveAimAxis" 
		-longName "curveAimAxis" -minValue 0 -maxValue 2 -enumName "X:Y:Z" -attributeType "enum";
	addAttr -readable false -cachedInternally true -keyable true -shortName "curveUpAxis" 
		-longName "curveUpAxis" -minValue 0 -maxValue 2 -enumName "X:Y:Z" -attributeType "enum";
	addAttr -readable false -cachedInternally true -keyable true -shortName "scaleMethod" 
		-longName "scaleMethod" -minValue 0 -maxValue 2 -enumName "Square Root:Linear:Cosine" 
		-attributeType "enum";
	addAttr -writable false -storable false -keyable true -shortName "asss" -longName "asss" 
		-attributeType "double";
	setAttr ".expression" -type "string" (
		"# Name: Re-rootable Quaternion Spine\n# Author: Eric Vignola - eric.vignola@gmail.com\n# \n# Demonstrates: - Persistant (flagged as storable) and non persistent attributes\n#               - Node awareness of number of connected outputs\n#               - Usage of a nurbsCurve type attribute to gather information such as the curve's length\n#\n# Explanation: This is an example of a so called \"quaternion spine\". Locators control the spine and transforms\n#              connected to the outputs will be driven by the spine.\n#              \n#              This spine features several things:\n#              - The spine can maintain its default length, or stretch (using the stretch node attribute)\n#              - When not stretched, the node can be rooted at any point (using the pivot node attribute)\n#              - Transforms moved on the spine can have their orientations changed via the aim/up axis node attributes\n#              - Transforms moved on the spine will inherit the transformations of the control points.\n#\n# For fun: - Select the driving locator and drag it around to see the effect.\n"
		+ "#          - Change the pivot attribute to reroot the spine\n#          - Change the scale attribute to scale from pivot position\n#          - Change the shift attribute to shift along the spine\n#          - Change the stretch attribute to keep the spine length when controls are pulled\n#          - Change the scale method to interpolate scale using sqrt (maya's way), linear or cosine\n#          - Select a spine transform (the cubes), and change it's U parameter to affect its position along the spine.\n\n\n\nfrom bisect import bisect_left as bl\nimport math\nimport maya.api.OpenMaya as om\n\ndef vectorToMatrix(V0, V1, aim_axis=0, up_axis=1):\n    \"\"\" Computes an orthogonal 4x4 matrix from an \"aim_vector\" (V0) and an \"up_vector\" (V1).\n        aim/up_axis defined as indices such as 0=X, 1=Y, 2=Z.\n        \n        There might be something built-in that does this, but couldn't find anything\n    \"\"\"\n\n    # Make sure vectors are unit\n    zero = om.MVector()\n    V0 = V0.normal()\n    V1 = V1.normal()\n    V2 = (V1^V0).normalize()\n"
		+ "    V1 = (V0^V2).normalize()\n\n    # Figure out which axis we're trying to extrapolate\n    right_axis = (min([aim_axis,up_axis])-max([aim_axis,up_axis])+min([aim_axis,up_axis]))%3\n    flip = 0\n    if aim_axis == 0 and up_axis == 2:\n        flip = 1\n    elif aim_axis == 1 and up_axis == 0:\n        flip = 1\n    elif aim_axis == 2 and up_axis == 1:\n        flip = 1\n\n    # Compose final matrix from given vectors, there might be a better to do this.\n    aim_axis*=4\n    up_axis*=4\n    right_axis*=4\n    \n    XYZ = om.MMatrix()\n    for i in range(3):\n        XYZ[aim_axis+i]   = V0[i]\n        XYZ[up_axis+i]    = V1[i]\n        \n        if flip:\n            XYZ[right_axis+i] = 0 - V2[i]\n        else:\n            XYZ[right_axis+i] = V2[i]\n        \n    return XYZ\n\n\ndef vectorSlerp(V0, V1, weight):\n    \"\"\" slerps between two vectors (there's probably a direct API call for this)\n    \"\"\"\n\n    # compute the angle between the vectors\n    dot   = V0.normal() * V1.normal()\n    dot   = max(min(dot, 1), -1)\n    angle = math.acos(dot)\n"
		+ "    \n    if angle == 0:\n        return V0\n    elif math.degrees(angle) == 180:\n        return V1\n    \n    return ((V0*math.sin((1-weight)*angle)) + (V1*math.sin(weight*angle)))/math.sin(angle)\n    \n\n\n\n\n\n#---------------------- Main ----------------------#\n\n\n# Get the current curve length from its highest parameter\nmax_parameter = inputCurve.findParamFromLength(10**9)\ncurrentLength = inputCurve.findLengthFromParam(max_parameter)\n\n\n# Reset default length if required\nif resetDefaultLength:\n    self.defaultLength = currentLength\n\n\n# Calcullate end points and end tangents for projections beyond the curve's limits\nt0 = inputCurve.tangent(0, space=om.MSpace.kWorld)\nt1 = inputCurve.tangent(max_parameter, space=om.MSpace.kWorld)\n\np0 = inputCurve.getPointAtParam(0,space=om.MSpace.kWorld)\np1 = inputCurve.getPointAtParam(max_parameter,space=om.MSpace.kWorld)\n\n\n\n# Calculate normalized control parameters to be used as a control key\nkeys = [0]\nM    = []\nfor i in range(len(controlMatrices)):\n    M.append(om.MTransformationMatrix(controlMatrices[i]))\n"
		+ "    \n    if i > 0:\n        dist = om.MPoint(M[i].translation(om.MSpace.kWorld)).distanceTo(om.MPoint(M[i-1].translation(om.MSpace.kWorld))) + keys[i-1]\n        keys.append(dist)\n\nfor i in range(1, len(keys)):\n    keys[i] /= keys[-1]\n\n\n\n# Calculate curve length ratio and delta to calculate stretch\nratio = self.defaultLength/currentLength\ndelta = (currentLength - self.defaultLength) / currentLength\n\n\n# Process each spine transform\nfor i in range(len(outputTranslate)):\n    \n    \n    # -- POSITION -- #\n    u = shift + pivot + (((((samples[i]*ratio + delta*pivot) * (1 - stretch)) + samples[i]*stretch) - pivot) * scale)\n    w = inputCurve.findParamFromLength(u*currentLength)\n\n    # If query is outside curve borders, use a projection\n    if u < 0:\n        outputTranslate[i] = (p0 + t0 * (u * currentLength))\n\n    elif u > 1:\n        outputTranslate[i] = (p1 + t1 * ((u-1) * currentLength))\n        \n    else:\n        outputTranslate[i] = (inputCurve.getPointAtParam(w,space=om.MSpace.kWorld))\n\n\n\n    # -- ROTATION -- #\n\n    # Find lower bound index\n"
		+ "    index = bl(keys,u)-1\n    if index < 0:\n        index = 0\n    elif index == len(keys)-1:\n        index -= 1\n        \n    \n\n    # Get the up vectors on each border\n    up0 = om.MVector(list(M[index].asMatrix())[4*curveUpAxis:4*(curveUpAxis+1)-1])\n    up1 = om.MVector(list(M[index+1].asMatrix())[4*curveUpAxis:4*(curveUpAxis+1)-1])\n\n    blend = (u - keys[index]) / (keys[index+1] - keys[index])\n    blend = max(min(blend, 1), 0)\n\n    normal = vectorSlerp(up0, up1, blend)\n    tangent = inputCurve.tangent(w, space=om.MSpace.kWorld)\n\n    if curveInvertUpAxis:\n        normal = om.MVector([0,0,0])-normal\n        \n    if curveInvertAimAxis:\n        tangent = om.MVector([0,0,0])-tangent\n        \n\n    outputRotate[i] = om.MTransformationMatrix(vectorToMatrix(tangent,\n                                                              normal,\n                                                              curveAimAxis,\n                                                              curveUpAxis)).rotation()\n    \n\n\n    # -- SCALE -- #\n"
		+ "\n    # sqrt\n    if scaleMethod == 0:\n        s0 = om.MVector([abs(x) ** (1-blend) for x in M[index].scale(om.MSpace.kWorld)])\n        s1 = om.MVector([abs(x) **    blend  for x in M[index+1].scale(om.MSpace.kWorld)])\n        outputScale[i] = [a*b for a,b in zip(s0,s1)]\n\n    # linear/cosine\n    else:\n        if scaleMethod == 2:\n            blend = 1-((math.cos(math.radians(blend*180))+1)*0.5)\n        \n        outputScale[i] = (om.MVector(M[index+1].scale(om.MSpace.kWorld)) * blend) + (om.MVector(M[index].scale(om.MSpace.kWorld)) * (1-blend))\n\n\n");
	setAttr "._inputAttrs" -type "string" "gAJ9cQEoWAUAAABzY2FsZV1xAlgFAAAAZmxvYXRxA2FYBwAAAHN0cmV0Y2hdcQRYBQAAAGZsb2F0\ncQVhWAUAAABzaGlmdF1xBlgFAAAAZmxvYXRxB2FYEQAAAGN1cnZlSW52ZXJ0VXBBeGlzXXEIWAQA\nAABlbnVtcQlhWBIAAABjdXJ2ZUludmVydEFpbUF4aXNdcQpYBAAAAGVudW1xC2FYDwAAAGNvbnRy\nb2xNYXRyaWNlc11xDFgGAAAAbWF0cml4cQ1hWAsAAABzY2FsZU1ldGhvZHEOXXEPWAQAAABlbnVt\ncRBhWAcAAABzYW1wbGVzXXERWAUAAABmbG9hdHESYVgFAAAAcGl2b3RdcRNYBQAAAGZsb2F0cRRh\nWAsAAABjdXJ2ZVVwQXhpc11xFVgEAAAAZW51bXEWYVUKaW5wdXRDdXJ2ZV1xF1UKbnVyYnNDdXJ2\nZXEYYVgSAAAAcmVzZXREZWZhdWx0TGVuZ3RoXXEZWAQAAABlbnVtcRphWAwAAABjdXJ2ZUFpbUF4\naXNdcRtYBAAAAGVudW1xHGF1Lg==\n";
	setAttr "._outputAttrs" -type "string" "gASVaQAAAAAAAAB9lCiMC291dHB1dFNjYWxllF2UjAZ2ZWN0b3KUYYwPb3V0cHV0VHJhbnNsYXRl\nlF2UjAZ2ZWN0b3KUYYwMb3V0cHV0Um90YXRllF2UjAVldWxlcpRhjARhc3NzlF2UjAVmbG9hdJRh\ndS4=\n";
	setAttr "._storedVarNames" -type "string" "gASVFAAAAAAAAABdlIwNZGVmYXVsdExlbmd0aJRhLg==\n";
	setAttr "._storedVarsData" -type "string" "gASVHQAAAAAAAAB9lIwNZGVmYXVsdExlbmd0aJRHQCgAAAAAAABzLg==\n";
	setAttr -keyable on ".inputCurve";
	setAttr -size 5 ".controlMatrices";
	setAttr -keyable on ".controlMatrices[0]";
	setAttr -keyable on ".controlMatrices[1]";
	setAttr -keyable on ".controlMatrices[2]";
	setAttr -keyable on ".controlMatrices[3]";
	setAttr -keyable on ".controlMatrices[4]";
	setAttr -keyable on ".controlMatrices";
	setAttr -size 11 ".outputScale";
	setAttr -size 11 ".outputRotate";
	setAttr -size 11 ".outputTranslate";
	setAttr -keyable on ".stretch";
	setAttr -keyable on ".pivot";
	setAttr -keyable on ".shift";
	setAttr -keyable on ".scale";
	setAttr -size 11 -keyable on ".samples";
	setAttr -size 11 -keyable on ".samples";
	setAttr -keyable on ".resetDefaultLength";
	setAttr -keyable on ".curveInvertAimAxis";
	setAttr -keyable on ".curveInvertUpAxis";
	setAttr -keyable on ".curveAimAxis";
	setAttr -keyable on ".curveUpAxis";
	setAttr -keyable on ".scaleMethod";
createNode polyCube -name "polyCube1";
	rename -uuid "F5B8A29D-47E9-4DF6-040A-FF9F753EB9D4";
	setAttr ".createUVs" 4;
createNode script -name "sceneConfigurationScriptNode";
	rename -uuid "DE2B8F22-40CF-ACEC-9C0B-D5AD9C941373";
	setAttr ".before" -type "string" "playbackOptions -min 0 -max 200 -ast 0 -aet 200 ";
	setAttr ".scriptType" 6;
createNode animCurveTU -name "pCube11_u";
	rename -uuid "51E77AD4-4101-466A-8067-4D88BCBB2D37";
	setAttr ".tangentType" 18;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "pCube1_u";
	rename -uuid "A7F27170-46B8-82D2-1CAE-B1ACDE84BB52";
	setAttr ".tangentType" 18;
	setAttr ".keyTimeValue[0]"  0 0;
createNode animCurveTU -name "pCube2_u";
	rename -uuid "2856B004-44CE-F187-9FD8-A7BE05F2C55B";
	setAttr ".tangentType" 18;
	setAttr ".keyTimeValue[0]"  0 0.1;
createNode animCurveTU -name "pCube3_u";
	rename -uuid "87FA9512-421B-5996-DC7B-0BB0F2E5F8C4";
	setAttr ".tangentType" 18;
	setAttr ".keyTimeValue[0]"  0 0.2;
createNode animCurveTU -name "pCube4_u";
	rename -uuid "933F97ED-4236-5615-7539-AC8BD9F6E67A";
	setAttr ".tangentType" 18;
	setAttr ".keyTimeValue[0]"  0 0.3;
createNode animCurveTU -name "pCube5_u";
	rename -uuid "36937CB6-40F7-FD06-FA2C-A994951B3DE2";
	setAttr ".tangentType" 18;
	setAttr ".keyTimeValue[0]"  0 0.4;
createNode animCurveTU -name "pCube6_u";
	rename -uuid "1707FFB0-49C8-5A87-18FF-179E4653459D";
	setAttr ".tangentType" 18;
	setAttr ".keyTimeValue[0]"  0 0.5;
createNode animCurveTU -name "pCube7_u";
	rename -uuid "C34C6AA1-465E-7CB9-76D7-5595DEEEA44A";
	setAttr ".tangentType" 18;
	setAttr ".keyTimeValue[0]"  0 0.6;
createNode animCurveTU -name "pCube8_u";
	rename -uuid "E8374708-4CE8-6087-497F-C2AF43A10C94";
	setAttr ".tangentType" 18;
	setAttr ".keyTimeValue[0]"  0 0.7;
createNode animCurveTU -name "pCube9_u";
	rename -uuid "921E2089-4ECB-A8FF-1416-1CA2D4DE77E6";
	setAttr ".tangentType" 18;
	setAttr ".keyTimeValue[0]"  0 0.8;
createNode animCurveTU -name "pCube10_u";
	rename -uuid "12E88FBE-4667-6CE5-CC9F-79A29DAF30E9";
	setAttr ".tangentType" 18;
	setAttr ".keyTimeValue[0]"  0 0.9;
createNode animCurveTL -name "locator1_translateX";
	rename -uuid "BECC19FF-457B-006B-7BAD-02BAFDAC7396";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 20 6.0454906314255314 80 -6.045491;
createNode animCurveTL -name "locator1_translateY";
	rename -uuid "10300BAC-4A54-DC16-CFAA-0C91A4FBBFD3";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 20 0 80 0;
createNode animCurveTL -name "locator1_translateZ";
	rename -uuid "E9CFA072-49D8-91D7-11D8-3D949B3FD83D";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 20 0 80 0;
createNode animCurveTL -name "locator2_translateX";
	rename -uuid "AA035918-4D45-3D8E-9E3D-26AEF55E1B8E";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 20 6.0454906314255314 80 -6.045491;
createNode animCurveTL -name "locator2_translateY";
	rename -uuid "71DCAAC2-453F-051C-749B-8AB7AD8EF19F";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 3 20 3 80 3;
createNode animCurveTL -name "locator2_translateZ";
	rename -uuid "489BE6EA-4954-5AD4-1911-5E90DC1CC4DC";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 20 0 80 0;
createNode animCurveTL -name "locator3_translateX";
	rename -uuid "8569D079-4880-0504-0C50-0297BCE02611";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 2 ".keyTimeValue[0:1]"  0 0 40 0;
createNode animCurveTL -name "locator3_translateY";
	rename -uuid "7EE0CF06-4E32-D53F-F4E1-97ADF4EE5A93";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 2 ".keyTimeValue[0:1]"  0 6 40 6;
createNode animCurveTL -name "locator3_translateZ";
	rename -uuid "F1080378-43D1-D0EC-BFF2-4CA46C875339";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 2 ".keyTimeValue[0:1]"  0 0 40 0;
createNode animCurveTL -name "locator4_translateX";
	rename -uuid "F66970BD-448C-EA6E-51A3-7FB43D93C072";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 20 -3.3176735008360585 80 3.317674;
createNode animCurveTL -name "locator4_translateY";
	rename -uuid "E9172E7B-4D0E-C487-4B61-11A1297D68B4";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 9 20 9 80 9;
createNode animCurveTL -name "locator4_translateZ";
	rename -uuid "F50EA478-4CE5-BF98-5463-1C9174C94DCA";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 20 0 80 0;
createNode animCurveTL -name "locator5_translateX";
	rename -uuid "0CFA8EAE-4DF4-062A-5146-B3907EE9374B";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 20 -3.3176735008360585 80 3.317674;
createNode animCurveTL -name "locator5_translateY";
	rename -uuid "404DEEA1-4E06-0BC2-5D84-D694ECBA6957";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 12 20 12 80 12;
createNode animCurveTL -name "locator5_translateZ";
	rename -uuid "645D5216-4271-E87B-2C16-5E893E07FD4A";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 20 0 80 0;
createNode animCurveTA -name "locator1_rotateX";
	rename -uuid "94E1963C-4BB9-B084-D43B-69878CEA9B0C";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 60 0 80 0;
createNode animCurveTA -name "locator1_rotateY";
	rename -uuid "EBE7D44F-4E7B-3643-BDC8-92A7CE428DBA";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 60 0 80 -44.576369988556721;
createNode animCurveTA -name "locator1_rotateZ";
	rename -uuid "CC424490-44FA-8439-5DD8-3F90987D2369";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 60 0 80 0;
createNode animCurveTA -name "locator2_rotateX";
	rename -uuid "ADB6FB97-43A4-615B-3301-BAACFDEEA4DD";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 60 0 80 0;
createNode animCurveTA -name "locator2_rotateY";
	rename -uuid "9C3FFBB4-4A32-C514-D699-25A1E7CEC992";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 60 0 80 -44.576369988556721;
createNode animCurveTA -name "locator2_rotateZ";
	rename -uuid "6EC6F9F9-4600-5925-53D0-78BF3C3C50ED";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 0 60 0 80 0;
createNode animCurveTA -name "locator3_rotateX";
	rename -uuid "2FC3C3D8-40FB-8ECF-1734-7AAA39A4D4C4";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 2 ".keyTimeValue[0:1]"  0 0 80 -15.279070014223924;
createNode animCurveTA -name "locator3_rotateY";
	rename -uuid "3C85DDD4-41AE-E091-5C19-B1ADD947540E";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 2 ".keyTimeValue[0:1]"  0 0 80 -31.552804620360615;
createNode animCurveTA -name "locator3_rotateZ";
	rename -uuid "7BA078B5-4BAA-DF31-51A7-E19C1C2DA699";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 2 ".keyTimeValue[0:1]"  0 0 80 -9.1658922985753826;
createNode animCurveTA -name "locator4_rotateX";
	rename -uuid "DBBF108A-46A3-AD16-B48B-5A9883D581FC";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 0;
createNode animCurveTA -name "locator4_rotateY";
	rename -uuid "E07F039F-42B2-C0D3-8AD4-6C90D9B98390";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 0;
createNode animCurveTA -name "locator4_rotateZ";
	rename -uuid "9F56497A-4F3C-38F2-F6C4-F38CCEB093EA";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 0;
createNode animCurveTA -name "locator5_rotateX";
	rename -uuid "D53B0C38-4313-D503-B32A-B48147BD2C3A";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 0;
createNode animCurveTA -name "locator5_rotateY";
	rename -uuid "FA6FE793-4D99-0A0A-39EE-49A4F358D631";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 0;
createNode animCurveTA -name "locator5_rotateZ";
	rename -uuid "D6AD0994-4BCD-3F7F-2255-C08E2A386264";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 0;
createNode animCurveTU -name "locator1_scaleX";
	rename -uuid "F668E97C-4DAA-74C7-585C-9D899B6C07B8";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "locator1_scaleY";
	rename -uuid "5FAB4CE8-420D-57A8-050D-39B234870B9E";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "locator1_scaleZ";
	rename -uuid "D86153AD-4CC6-B0DE-8ADD-98A8BD360238";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "locator2_scaleX";
	rename -uuid "E178D541-4E9B-CC0B-7E40-C7A75491F38E";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "locator2_scaleY";
	rename -uuid "023BCB5E-4F8C-94EE-7556-C4BF45691374";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "locator2_scaleZ";
	rename -uuid "BFEF1ED1-40C3-3534-DAC4-BAA4C764717F";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "locator3_scaleX";
	rename -uuid "86A47697-49FE-1EA6-67ED-42A1F6BAE9B5";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 1 80 1 120 4.5536121774104936;
createNode animCurveTU -name "locator3_scaleY";
	rename -uuid "93F06F74-4CB3-8B35-41C4-30AC96376FB2";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 1 80 1 120 0.41597802010561391;
createNode animCurveTU -name "locator3_scaleZ";
	rename -uuid "21E137AC-47FA-3BB6-B5B3-6DA77F09E61B";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  0 1 80 1 120 4.5536121774104936;
createNode animCurveTU -name "locator4_scaleX";
	rename -uuid "9C3AE69B-49C6-8543-8D4E-FB9FC31BBAC1";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "locator4_scaleY";
	rename -uuid "C73CC79F-4EB2-4E4D-0174-C9954CF8DD9F";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "locator4_scaleZ";
	rename -uuid "CC192FBE-42D2-256B-6D88-389937FA89D5";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "locator5_scaleX";
	rename -uuid "4BF0EF57-4253-9CD2-66CA-1E8DF7D8BB0B";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "locator5_scaleY";
	rename -uuid "D0EA66E7-48E6-E153-9A9A-B5988DAD4D47";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "locator5_scaleZ";
	rename -uuid "9B18D546-4E1D-EEB0-500C-54A5D0E1BBCA";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr ".keyTimeValue[0]"  0 1;
createNode animCurveTU -name "curve1_pivot";
	rename -uuid "C158E25F-4551-001B-2F17-E281A451AAA2";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 2 ".keyTimeValue[0:1]"  20 0 40 1;
createNode animCurveTU -name "curve1_shift";
	rename -uuid "EB5A5546-466C-020D-9D58-059BBEC1FD8D";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  120 0 160 0.37700000000000006
		 200 -0.467;
select -noExpand :time1;
	setAttr -alteredValue -keyable on ".caching";
	setAttr -alteredValue -channelBox on ".isHistoricallyInteresting";
	setAttr -alteredValue -keyable on ".nodeState";
	setAttr -channelBox on ".binMembership";
	setAttr -keyable on ".outTime" 0;
	setAttr -alteredValue -keyable on ".unwarpedTime";
	setAttr -keyable on ".enableTimewarp";
	setAttr -alteredValue -keyable on ".timecodeProductionStart";
	setAttr -alteredValue -keyable on ".timecodeMayaStart";
select -noExpand :hardwareRenderingGlobals;
	setAttr -keyable on ".isHistoricallyInteresting";
	setAttr -keyable on ".transparencyQuality";
	setAttr ".enableTextureMaxRes" no;
	setAttr ".textureMaxResolution" 4096;
	setAttr -alteredValue ".ssaoAmount";
	setAttr -alteredValue ".ssaoRadius";
	setAttr -alteredValue ".motionBlurEnable";
	setAttr -alteredValue -keyable on ".motionBlurShutterOpenFraction";
	setAttr ".floatingPointRTEnable" yes;
select -noExpand :renderPartition;
	setAttr -alteredValue -keyable on ".caching";
	setAttr -channelBox on ".isHistoricallyInteresting";
	setAttr -alteredValue -keyable on ".nodeState";
	setAttr -channelBox on ".binMembership";
	setAttr -size 2 ".sets";
	setAttr -channelBox on ".annotation";
	setAttr -channelBox on ".partitionType";
select -noExpand :renderGlobalsList1;
	setAttr -keyable on ".caching";
	setAttr -channelBox on ".isHistoricallyInteresting";
	setAttr -keyable on ".nodeState";
	setAttr -channelBox on ".binMembership";
select -noExpand :defaultShaderList1;
	setAttr -keyable on ".caching";
	setAttr -channelBox on ".isHistoricallyInteresting";
	setAttr -keyable on ".nodeState";
	setAttr -channelBox on ".binMembership";
	setAttr -size 5 ".shaders";
select -noExpand :postProcessList1;
	setAttr -keyable on ".caching";
	setAttr -channelBox on ".isHistoricallyInteresting";
	setAttr -keyable on ".nodeState";
	setAttr -channelBox on ".binMembership";
	setAttr -size 2 ".postProcesses";
select -noExpand :defaultRenderingList1;
	setAttr -keyable on ".isHistoricallyInteresting";
select -noExpand :initialShadingGroup;
	setAttr -alteredValue -keyable on ".caching";
	setAttr -channelBox on ".isHistoricallyInteresting";
	setAttr -alteredValue -keyable on ".nodeState";
	setAttr -channelBox on ".binMembership";
	setAttr -size 11 ".dagSetMembers";
	setAttr -keyable on ".memberWireframeColor";
	setAttr -channelBox on ".annotation";
	setAttr -channelBox on ".isLayer";
	setAttr -channelBox on ".verticesOnlySet";
	setAttr -channelBox on ".edgesOnlySet";
	setAttr -channelBox on ".facetsOnlySet";
	setAttr -channelBox on ".editPointsOnlySet";
	setAttr -keyable on ".renderableOnlySet";
select -noExpand :defaultRenderGlobals;
	addAttr -cachedInternally true -hidden true -shortName "dss" -longName "defaultSurfaceShader" 
		-dataType "string";
	setAttr -keyable on ".caching";
	setAttr -channelBox on ".isHistoricallyInteresting";
	setAttr -keyable on ".nodeState";
	setAttr -channelBox on ".binMembership";
	setAttr -keyable on ".macCodec";
	setAttr -keyable on ".macDepth";
	setAttr -keyable on ".macQual";
	setAttr -keyable on ".comFrrt";
	setAttr -channelBox on ".ignoreFilmGate";
	setAttr -keyable on ".clipFinalShadedColor";
	setAttr -keyable on ".enableDepthMaps";
	setAttr -keyable on ".enableDefaultLight";
	setAttr -channelBox on ".currentRenderer";
	setAttr -alteredValue -keyable on ".enableStrokeRender";
	setAttr -keyable on ".onlyRenderStrokes";
	setAttr -channelBox on ".strokesDepthFile";
	setAttr -alteredValue -keyable on ".imageFormat";
	setAttr -channelBox on ".imfPluginKey";
	setAttr -keyable on ".gammaCorrection";
	setAttr -channelBox on ".animation";
	setAttr -channelBox on ".animationRange";
	setAttr -keyable on ".startFrame";
	setAttr -keyable on ".endFrame";
	setAttr -alteredValue -keyable on ".byFrameStep";
	setAttr -channelBox on ".modifyExtension";
	setAttr -channelBox on ".startExtension";
	setAttr -keyable on ".byExtension";
	setAttr -channelBox on ".extensionPadding";
	setAttr -keyable on ".fieldExtControl";
	setAttr -alteredValue -keyable on ".outFormatControl";
	setAttr -channelBox on ".oddFieldExt";
	setAttr -channelBox on ".evenFieldExt";
	setAttr -channelBox on ".outFormatExt";
	setAttr -channelBox on ".useMayaFileName";
	setAttr -channelBox on ".useFrameExt";
	setAttr -channelBox on ".putFrameBeforeExt";
	setAttr -channelBox on ".periodInExt";
	setAttr -channelBox on ".imageFilePrefix";
	setAttr -keyable on ".renderVersion";
	setAttr -keyable on ".composite";
	setAttr -keyable on ".compositeThreshold";
	setAttr -keyable on ".shadowsObeyLightLinking";
	setAttr -channelBox on ".shadowsObeyShadowLinking";
	setAttr -keyable on ".recursionDepth";
	setAttr -keyable on ".leafPrimitives";
	setAttr -alteredValue -keyable on ".subdivisionPower";
	setAttr -keyable on ".subdivisionHashSize";
	setAttr -alteredValue -keyable on ".logRenderPerformance";
	setAttr -channelBox on ".geometryVector";
	setAttr -channelBox on ".shadingVector";
	setAttr -keyable on ".maximumMemory";
	setAttr -keyable on ".numCpusToUse";
	setAttr -keyable on ".interruptFrequency";
	setAttr -keyable on ".shadowPass";
	setAttr -channelBox on ".iprShadowPass";
	setAttr -keyable on ".useFileCache";
	setAttr -keyable on ".optimizeInstances";
	setAttr -keyable on ".reuseTessellations";
	setAttr -keyable on ".matteOpacityUsesTransparency";
	setAttr -alteredValue -keyable on ".motionBlur";
	setAttr -alteredValue -keyable on ".motionBlurByFrame";
	setAttr -keyable on ".motionBlurShutterOpen";
	setAttr -keyable on ".motionBlurShutterClose";
	setAttr -alteredValue -keyable on ".applyFogInPost";
	setAttr -keyable on ".postFogBlur";
	setAttr -keyable on ".preMel";
	setAttr -keyable on ".postMel";
	setAttr -keyable on ".preRenderLayerMel";
	setAttr -keyable on ".postRenderLayerMel";
	setAttr -channelBox on ".preRenderMel";
	setAttr -channelBox on ".postRenderMel";
	setAttr -channelBox on ".preFurRenderMel";
	setAttr -channelBox on ".postFurRenderMel";
	setAttr -alteredValue -keyable on ".blurLength";
	setAttr -alteredValue -keyable on ".blurSharpness";
	setAttr -alteredValue -keyable on ".smoothValue";
	setAttr -keyable on ".useBlur2DMemoryCap";
	setAttr -keyable on ".blur2DMemoryCap";
	setAttr -channelBox on ".motionBlurType";
	setAttr -keyable on ".useDisplacementBoundingBox";
	setAttr -keyable on ".smoothColor";
	setAttr -keyable on ".keepMotionVector";
	setAttr -channelBox on ".iprRenderShading";
	setAttr -channelBox on ".iprRenderShadowMaps";
	setAttr -channelBox on ".iprRenderMotionBlur";
	setAttr -keyable on ".renderLayerEnable";
	setAttr -alteredValue -keyable on ".forceTileSize";
	setAttr -keyable on ".tileWidth";
	setAttr -keyable on ".tileHeight";
	setAttr -keyable on ".jitterFinalColor";
	setAttr -channelBox on ".raysSeeBackground";
	setAttr -keyable on ".oversamplePaintEffects";
	setAttr -keyable on ".oversamplePfxPostFilter";
	setAttr -keyable on ".renderingColorProfile";
	setAttr -keyable on ".inputColorProfile";
	setAttr -keyable on ".outputColorProfile";
	setAttr -channelBox on ".hyperShadeBinList";
	setAttr ".defaultSurfaceShader" -type "string" "lambert1";
select -noExpand :defaultColorMgtGlobals;
	setAttr ".configFileEnabled" yes;
	setAttr ".configFilePath" -type "string" "<MAYA_RESOURCES>/OCIO-configs/Maya-legacy/config.ocio";
	setAttr ".viewTransformName" -type "string" "sRGB gamma (legacy)";
	setAttr ".viewName" -type "string" "sRGB gamma";
	setAttr ".displayName" -type "string" "legacy";
	setAttr ".workingSpaceName" -type "string" "scene-linear Rec 709/sRGB";
	setAttr ".outputUseViewTransform" no;
	setAttr ".playblastOutputUseViewTransform" no;
	setAttr ".outputTransformName" -type "string" "sRGB gamma (legacy)";
	setAttr ".playblastOutputTransformName" -type "string" "sRGB gamma (legacy)";
connectAttr "curve1_pivot.output" "curve1.pivot";
connectAttr "curve1_shift.output" "curve1.shift";
connectAttr "cluster5.outputGeometry[0]" "curveShape1.create";
connectAttr "tweak1.plist[0].controlPoints[0]" "curveShape1.tweakLocation";
connectAttr "cluster1GroupId.groupId" "curveShape1.instObjGroups.objectGroups[0].objectGroupId"
		;
connectAttr "cluster1Set.memberWireframeColor" "curveShape1.instObjGroups.objectGroups[0].objectGrpColor"
		;
connectAttr "groupId2.groupId" "curveShape1.instObjGroups.objectGroups[1].objectGroupId"
		;
connectAttr "tweakSet1.memberWireframeColor" "curveShape1.instObjGroups.objectGroups[1].objectGrpColor"
		;
connectAttr "cluster2GroupId.groupId" "curveShape1.instObjGroups.objectGroups[2].objectGroupId"
		;
connectAttr "cluster2Set.memberWireframeColor" "curveShape1.instObjGroups.objectGroups[2].objectGrpColor"
		;
connectAttr "cluster3GroupId.groupId" "curveShape1.instObjGroups.objectGroups[3].objectGroupId"
		;
connectAttr "cluster3Set.memberWireframeColor" "curveShape1.instObjGroups.objectGroups[3].objectGrpColor"
		;
connectAttr "cluster4GroupId.groupId" "curveShape1.instObjGroups.objectGroups[4].objectGroupId"
		;
connectAttr "cluster4Set.memberWireframeColor" "curveShape1.instObjGroups.objectGroups[4].objectGrpColor"
		;
connectAttr "cluster5GroupId.groupId" "curveShape1.instObjGroups.objectGroups[5].objectGroupId"
		;
connectAttr "cluster5Set.memberWireframeColor" "curveShape1.instObjGroups.objectGroups[5].objectGrpColor"
		;
connectAttr "locator1_translateX.output" "locator1.translateX";
connectAttr "locator1_translateY.output" "locator1.translateY";
connectAttr "locator1_translateZ.output" "locator1.translateZ";
connectAttr "locator1_rotateX.output" "locator1.rotateX";
connectAttr "locator1_rotateY.output" "locator1.rotateY";
connectAttr "locator1_rotateZ.output" "locator1.rotateZ";
connectAttr "locator1_scaleX.output" "locator1.scaleX";
connectAttr "locator1_scaleY.output" "locator1.scaleY";
connectAttr "locator1_scaleZ.output" "locator1.scaleZ";
connectAttr "locator2_translateX.output" "locator2.translateX";
connectAttr "locator2_translateY.output" "locator2.translateY";
connectAttr "locator2_translateZ.output" "locator2.translateZ";
connectAttr "locator2_scaleX.output" "locator2.scaleX";
connectAttr "locator2_scaleY.output" "locator2.scaleY";
connectAttr "locator2_scaleZ.output" "locator2.scaleZ";
connectAttr "locator2_rotateX.output" "locator2.rotateX";
connectAttr "locator2_rotateY.output" "locator2.rotateY";
connectAttr "locator2_rotateZ.output" "locator2.rotateZ";
connectAttr "locator3_translateX.output" "locator3.translateX";
connectAttr "locator3_translateY.output" "locator3.translateY";
connectAttr "locator3_translateZ.output" "locator3.translateZ";
connectAttr "locator3_scaleX.output" "locator3.scaleX";
connectAttr "locator3_scaleY.output" "locator3.scaleY";
connectAttr "locator3_scaleZ.output" "locator3.scaleZ";
connectAttr "locator3_rotateX.output" "locator3.rotateX";
connectAttr "locator3_rotateY.output" "locator3.rotateY";
connectAttr "locator3_rotateZ.output" "locator3.rotateZ";
connectAttr "locator4_translateX.output" "locator4.translateX";
connectAttr "locator4_translateY.output" "locator4.translateY";
connectAttr "locator4_translateZ.output" "locator4.translateZ";
connectAttr "locator4_rotateX.output" "locator4.rotateX";
connectAttr "locator4_rotateY.output" "locator4.rotateY";
connectAttr "locator4_rotateZ.output" "locator4.rotateZ";
connectAttr "locator4_scaleX.output" "locator4.scaleX";
connectAttr "locator4_scaleY.output" "locator4.scaleY";
connectAttr "locator4_scaleZ.output" "locator4.scaleZ";
connectAttr "locator5_translateX.output" "locator5.translateX";
connectAttr "locator5_translateY.output" "locator5.translateY";
connectAttr "locator5_translateZ.output" "locator5.translateZ";
connectAttr "locator5_rotateX.output" "locator5.rotateX";
connectAttr "locator5_rotateY.output" "locator5.rotateY";
connectAttr "locator5_rotateZ.output" "locator5.rotateZ";
connectAttr "locator5_scaleX.output" "locator5.scaleX";
connectAttr "locator5_scaleY.output" "locator5.scaleY";
connectAttr "locator5_scaleZ.output" "locator5.scaleZ";
connectAttr "pCube1_u.output" "pCube1.u";
connectAttr "spineNode.outputTranslate[0]" "pCube1.translate";
connectAttr "spineNode.outputScale[0]" "pCube1.scale";
connectAttr "spineNode.outputRotate[0]" "pCube1.rotate";
connectAttr "polyCube1.output" "pCubeShape1.inMesh";
connectAttr "pCube2_u.output" "pCube2.u";
connectAttr "spineNode.outputTranslate[1]" "pCube2.translate";
connectAttr "spineNode.outputScale[1]" "pCube2.scale";
connectAttr "spineNode.outputRotate[1]" "pCube2.rotate";
connectAttr "pCube3_u.output" "pCube3.u";
connectAttr "spineNode.outputTranslate[2]" "pCube3.translate";
connectAttr "spineNode.outputScale[2]" "pCube3.scale";
connectAttr "spineNode.outputRotate[2]" "pCube3.rotate";
connectAttr "pCube4_u.output" "pCube4.u";
connectAttr "spineNode.outputTranslate[3]" "pCube4.translate";
connectAttr "spineNode.outputScale[3]" "pCube4.scale";
connectAttr "spineNode.outputRotate[3]" "pCube4.rotate";
connectAttr "pCube5_u.output" "pCube5.u";
connectAttr "spineNode.outputTranslate[4]" "pCube5.translate";
connectAttr "spineNode.outputScale[4]" "pCube5.scale";
connectAttr "spineNode.outputRotate[4]" "pCube5.rotate";
connectAttr "pCube6_u.output" "pCube6.u";
connectAttr "spineNode.outputTranslate[5]" "pCube6.translate";
connectAttr "spineNode.outputScale[5]" "pCube6.scale";
connectAttr "spineNode.outputRotate[5]" "pCube6.rotate";
connectAttr "pCube7_u.output" "pCube7.u";
connectAttr "spineNode.outputTranslate[6]" "pCube7.translate";
connectAttr "spineNode.outputScale[6]" "pCube7.scale";
connectAttr "spineNode.outputRotate[6]" "pCube7.rotate";
connectAttr "pCube8_u.output" "pCube8.u";
connectAttr "spineNode.outputTranslate[7]" "pCube8.translate";
connectAttr "spineNode.outputScale[7]" "pCube8.scale";
connectAttr "spineNode.outputRotate[7]" "pCube8.rotate";
connectAttr "pCube9_u.output" "pCube9.u";
connectAttr "spineNode.outputTranslate[8]" "pCube9.translate";
connectAttr "spineNode.outputScale[8]" "pCube9.scale";
connectAttr "spineNode.outputRotate[8]" "pCube9.rotate";
connectAttr "pCube10_u.output" "pCube10.u";
connectAttr "spineNode.outputTranslate[9]" "pCube10.translate";
connectAttr "spineNode.outputScale[9]" "pCube10.scale";
connectAttr "spineNode.outputRotate[9]" "pCube10.rotate";
connectAttr "pCube11_u.output" "pCube11.u";
connectAttr "spineNode.outputTranslate[10]" "pCube11.translate";
connectAttr "spineNode.outputScale[10]" "pCube11.scale";
connectAttr "spineNode.outputRotate[10]" "pCube11.rotate";
relationship "link" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "link" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
connectAttr "layerManager.displayLayerId[0]" "defaultLayer.identification";
connectAttr "renderLayerManager.renderLayerId[0]" "defaultRenderLayer.identification"
		;
connectAttr "cluster1GroupParts.outputGeometry" "cluster1.input[0].inputGeometry"
		;
connectAttr "cluster1GroupId.groupId" "cluster1.input[0].groupId";
connectAttr "cluster1Handle.worldMatrix" "cluster1.matrix";
connectAttr "cluster1HandleShape.clusterTransforms" "cluster1.clusterXforms";
connectAttr "groupParts2.outputGeometry" "tweak1.input[0].inputGeometry";
connectAttr "groupId2.groupId" "tweak1.input[0].groupId";
connectAttr "cluster1GroupId.message" "cluster1Set.groupNodes" -nextAvailable;
connectAttr "curveShape1.instObjGroups.objectGroups[0]" "cluster1Set.dagSetMembers"
		 -nextAvailable;
connectAttr "cluster1.message" "cluster1Set.usedBy[0]";
connectAttr "tweak1.outputGeometry[0]" "cluster1GroupParts.inputGeometry";
connectAttr "cluster1GroupId.groupId" "cluster1GroupParts.groupId";
connectAttr "groupId2.message" "tweakSet1.groupNodes" -nextAvailable;
connectAttr "curveShape1.instObjGroups.objectGroups[1]" "tweakSet1.dagSetMembers"
		 -nextAvailable;
connectAttr "tweak1.message" "tweakSet1.usedBy[0]";
connectAttr "curveShape1Orig.worldSpace" "groupParts2.inputGeometry";
connectAttr "groupId2.groupId" "groupParts2.groupId";
connectAttr "cluster2GroupParts.outputGeometry" "cluster2.input[0].inputGeometry"
		;
connectAttr "cluster2GroupId.groupId" "cluster2.input[0].groupId";
connectAttr "cluster2Handle.worldMatrix" "cluster2.matrix";
connectAttr "cluster2HandleShape.clusterTransforms" "cluster2.clusterXforms";
connectAttr "cluster2GroupId.message" "cluster2Set.groupNodes" -nextAvailable;
connectAttr "curveShape1.instObjGroups.objectGroups[2]" "cluster2Set.dagSetMembers"
		 -nextAvailable;
connectAttr "cluster2.message" "cluster2Set.usedBy[0]";
connectAttr "cluster1.outputGeometry[0]" "cluster2GroupParts.inputGeometry";
connectAttr "cluster2GroupId.groupId" "cluster2GroupParts.groupId";
connectAttr "cluster3GroupParts.outputGeometry" "cluster3.input[0].inputGeometry"
		;
connectAttr "cluster3GroupId.groupId" "cluster3.input[0].groupId";
connectAttr "cluster3Handle.worldMatrix" "cluster3.matrix";
connectAttr "cluster3HandleShape.clusterTransforms" "cluster3.clusterXforms";
connectAttr "cluster3GroupId.message" "cluster3Set.groupNodes" -nextAvailable;
connectAttr "curveShape1.instObjGroups.objectGroups[3]" "cluster3Set.dagSetMembers"
		 -nextAvailable;
connectAttr "cluster3.message" "cluster3Set.usedBy[0]";
connectAttr "cluster2.outputGeometry[0]" "cluster3GroupParts.inputGeometry";
connectAttr "cluster3GroupId.groupId" "cluster3GroupParts.groupId";
connectAttr "cluster4GroupParts.outputGeometry" "cluster4.input[0].inputGeometry"
		;
connectAttr "cluster4GroupId.groupId" "cluster4.input[0].groupId";
connectAttr "cluster4Handle.worldMatrix" "cluster4.matrix";
connectAttr "cluster4HandleShape.clusterTransforms" "cluster4.clusterXforms";
connectAttr "cluster4GroupId.message" "cluster4Set.groupNodes" -nextAvailable;
connectAttr "curveShape1.instObjGroups.objectGroups[4]" "cluster4Set.dagSetMembers"
		 -nextAvailable;
connectAttr "cluster4.message" "cluster4Set.usedBy[0]";
connectAttr "cluster3.outputGeometry[0]" "cluster4GroupParts.inputGeometry";
connectAttr "cluster4GroupId.groupId" "cluster4GroupParts.groupId";
connectAttr "cluster5GroupParts.outputGeometry" "cluster5.input[0].inputGeometry"
		;
connectAttr "cluster5GroupId.groupId" "cluster5.input[0].groupId";
connectAttr "cluster5Handle.worldMatrix" "cluster5.matrix";
connectAttr "cluster5HandleShape.clusterTransforms" "cluster5.clusterXforms";
connectAttr "cluster5GroupId.message" "cluster5Set.groupNodes" -nextAvailable;
connectAttr "curveShape1.instObjGroups.objectGroups[5]" "cluster5Set.dagSetMembers"
		 -nextAvailable;
connectAttr "cluster5.message" "cluster5Set.usedBy[0]";
connectAttr "cluster4.outputGeometry[0]" "cluster5GroupParts.inputGeometry";
connectAttr "cluster5GroupId.groupId" "cluster5GroupParts.groupId";
connectAttr "pCube1.u" "spineNode.samples[0]";
connectAttr "pCube2.u" "spineNode.samples[1]";
connectAttr "pCube3.u" "spineNode.samples[2]";
connectAttr "pCube4.u" "spineNode.samples[3]";
connectAttr "pCube5.u" "spineNode.samples[4]";
connectAttr "pCube6.u" "spineNode.samples[5]";
connectAttr "pCube7.u" "spineNode.samples[6]";
connectAttr "pCube8.u" "spineNode.samples[7]";
connectAttr "pCube9.u" "spineNode.samples[8]";
connectAttr "pCube10.u" "spineNode.samples[9]";
connectAttr "pCube11.u" "spineNode.samples[10]";
connectAttr "curveShape1.worldSpace" "spineNode.inputCurve";
connectAttr "locatorShape1.worldMatrix" "spineNode.controlMatrices[0]";
connectAttr "locatorShape2.worldMatrix" "spineNode.controlMatrices[1]";
connectAttr "locatorShape3.worldMatrix" "spineNode.controlMatrices[2]";
connectAttr "locatorShape4.worldMatrix" "spineNode.controlMatrices[3]";
connectAttr "locatorShape5.worldMatrix" "spineNode.controlMatrices[4]";
connectAttr "curve1.stretch" "spineNode.stretch";
connectAttr "curve1.pivot" "spineNode.pivot";
connectAttr "curve1.shift" "spineNode.shift";
connectAttr "curve1.Scale" "spineNode.scale";
connectAttr "curve1.resetDefaultLength" "spineNode.resetDefaultLength";
connectAttr "curve1.curveInvertAimAxis" "spineNode.curveInvertAimAxis";
connectAttr "curve1.curveInvertUpAxis" "spineNode.curveInvertUpAxis";
connectAttr "curve1.curveAimAxis" "spineNode.curveAimAxis";
connectAttr "curve1.curveUpAxis" "spineNode.curveUpAxis";
connectAttr "curve1.scaleMethod" "spineNode.scaleMethod";
connectAttr "defaultRenderLayer.message" ":defaultRenderingList1.rendering" -nextAvailable
		;
connectAttr "pCubeShape1.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
connectAttr "pCubeShape2.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
connectAttr "pCubeShape3.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
connectAttr "pCubeShape4.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
connectAttr "pCubeShape5.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
connectAttr "pCubeShape6.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
connectAttr "pCubeShape7.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
connectAttr "pCubeShape8.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
connectAttr "pCubeShape9.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
connectAttr "pCubeShape10.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
connectAttr "pCubeShape11.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
// End of quaternionSpineNode.ma
