//Maya ASCII 2018ff08 scene
//Name: textMeshGeneratorNode.ma
//Last modified: Tue, Nov 13, 2018 08:02:25 AM
//Codeset: 1252
requires maya "2018ff08";
requires -nodeType "mPyNode" "mpynode_plugin.py" "1.0";
requires -nodeType "type" -nodeType "shellDeformer" -nodeType "vectorAdjust" -nodeType "vectorExtrude"
		 "Type" "2.0a";
requires "stereoCamera" "10.0";
currentUnit -linear centimeter -angle degree -time ntsc;
fileInfo "application" "maya";
fileInfo "product" "Maya 2018";
fileInfo "version" "2018";
fileInfo "cutIdentifier" "201804211841-f3d65dda2a";
fileInfo "osv" "Microsoft Windows 8 Business Edition, 64-bit  (Build 9200)\n";
createNode transform -shared -name "persp";
	rename -uuid "9D40400F-4B49-D0E5-D701-C49EBD94A40D";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 249.05955075498392 142.37688538647245 547.66163172878623 ;
	setAttr ".rotate" -type "double3" -14.138352729613196 16.600000000000293 0 ;
createNode camera -shared -name "perspShape" -parent "persp";
	rename -uuid "6AF21E50-47D7-73BB-7435-DC8AC789A745";
	setAttr -keyable off ".visibility" no;
	setAttr ".focalLength" 34.999999999999993;
	setAttr ".centerOfInterest" 651.21653979601683;
	setAttr ".imageName" -type "string" "persp";
	setAttr ".depthName" -type "string" "persp_depth";
	setAttr ".maskName" -type "string" "persp_mask";
	setAttr ".homeCommand" -type "string" "viewSet -p %camera";
createNode transform -shared -name "top";
	rename -uuid "560AD1B7-4BC8-3E4C-1021-1A8F18C7C847";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 0 1000.1 0 ;
	setAttr ".rotate" -type "double3" -89.999999999999986 0 0 ;
createNode camera -shared -name "topShape" -parent "top";
	rename -uuid "8500193D-4BF0-6725-C165-18888AC01BAB";
	setAttr -keyable off ".visibility" no;
	setAttr ".renderable" no;
	setAttr ".centerOfInterest" 1000.1;
	setAttr ".orthographicWidth" 30;
	setAttr ".imageName" -type "string" "top";
	setAttr ".depthName" -type "string" "top_depth";
	setAttr ".maskName" -type "string" "top_mask";
	setAttr ".homeCommand" -type "string" "viewSet -t %camera";
	setAttr ".orthographic" yes;
createNode transform -shared -name "front";
	rename -uuid "D02E6E64-485A-4535-1AC2-749A648926E8";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 0 0 1000.1 ;
createNode camera -shared -name "frontShape" -parent "front";
	rename -uuid "BF9EFD49-4942-2FAD-420A-24834D7A4456";
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
	rename -uuid "53C022EB-49C6-E650-67F8-0EB5CC5DDEC4";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 1000.1 0 0 ;
	setAttr ".rotate" -type "double3" 0 89.999999999999986 0 ;
createNode camera -shared -name "sideShape" -parent "side";
	rename -uuid "F9CE596B-4FE0-7752-4B98-89A65C5AD071";
	setAttr -keyable off ".visibility" no;
	setAttr ".renderable" no;
	setAttr ".centerOfInterest" 1000.1;
	setAttr ".orthographicWidth" 30;
	setAttr ".imageName" -type "string" "side";
	setAttr ".depthName" -type "string" "side_depth";
	setAttr ".maskName" -type "string" "side_mask";
	setAttr ".homeCommand" -type "string" "viewSet -s %camera";
	setAttr ".orthographic" yes;
createNode transform -name "typeMesh1";
	rename -uuid "B4CEAC87-4B5C-E208-4566-659724C6C161";
	setAttr ".translate" -type "double3" 46.430545226325421 80.895731818991464 58.139779432793461 ;
	setAttr -alteredValue ".translateX";
	setAttr -alteredValue ".translateY";
	setAttr -alteredValue ".translateZ";
createNode mesh -name "typeMeshShape1" -parent "typeMesh1";
	rename -uuid "64CB12B3-4899-0320-F1D7-A8AE11C12F18";
	setAttr -keyable off ".visibility";
	setAttr -size 8 ".instObjGroups[0].objectGroups";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
createNode mesh -name "typeMeshShape1Orig" -parent "typeMesh1";
	rename -uuid "35AD3A59-485A-7554-F031-76A13664663D";
	setAttr -keyable off ".visibility";
	setAttr ".intermediateObject" yes;
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
createNode lightLinker -shared -name "lightLinker1";
	rename -uuid "A4EFB4AF-426A-1C52-226C-4A927B39156D";
	setAttr -size 3 ".link";
	setAttr -size 3 ".shadowLink";
createNode shapeEditorManager -name "shapeEditorManager";
	rename -uuid "F3A8CA6C-4569-0DE0-F427-A98DF539A030";
createNode poseInterpolatorManager -name "poseInterpolatorManager";
	rename -uuid "B6D7A34F-482B-CE87-951B-698A679F1973";
createNode displayLayerManager -name "layerManager";
	rename -uuid "348BE89A-4F3D-E29D-DF8F-2D9021399BC6";
createNode displayLayer -name "defaultLayer";
	rename -uuid "9B15B107-44E6-F680-F097-889A90C1A5F8";
createNode renderLayerManager -name "renderLayerManager";
	rename -uuid "03BCF1E6-4F93-03DC-2307-DA932A30B3B8";
createNode renderLayer -name "defaultRenderLayer";
	rename -uuid "C9169327-43DA-17C0-54D8-0782636B9280";
	setAttr ".global" yes;
createNode type -name "type1";
	rename -uuid "1BD13673-4259-906A-9EA9-AEB5A2B2F647";
	setAttr ".solidsPerCharacter" -type "doubleArray" 46 1 1 1 1 1 1 1 1 1 1 1 1
		 2 1 2 1 1 1 1 1 1 1 1 1 1 2 1 1 1 1 1 1 1 1 1 1 2 1 1 1 1 1 1 1 1 1 ;
	setAttr ".solidsPerWord" -type "doubleArray" 10 4 2 8 3 9 3 9 3 9 0 ;
	setAttr ".solidsPerLine" -type "doubleArray" 5 14 12 12 12 0 ;
	setAttr ".vertsPerChar" -type "doubleArray" 46 50 89 100 152 165 177 188 227
		 291 333 343 393 403 415 423 437 518 522 536 601 649 699 713 763 772 780 893 941 945
		 1058 1147 1197 1215 1280 1331 1341 1349 1399 1512 1516 1522 1587 1676 1694 1712 1801 ;
	setAttr ".characterBoundingBoxesMax" -type "vectorArray" 46 9.0909090909090899
		 9.3506493506493502 0 17.79220779220779 9.3506493506493502 2.0292207792207792e-06 26.753246753246749
		 9.3506493506493502 4.0584415584415584e-06 35.194805194805191 9.3506493506493502 6.0876623376623368e-06 50.389610389610382
		 9.3506493506493502 1.0146103896103896e-05 58.181818181818173 9.3506493506493502 1.2175324675324674e-05 71.558441558441558
		 9.3506493506493502 1.6233766233766234e-05 79.740259740259731 9.3506493506493502 1.8262987012987013e-05 89.350649350649348
		 9.3506493506493502 2.0292207792207792e-05 97.922077922077918 9.3506493506493502 2.2321428571428568e-05 107.27272727272727
		 9.3506493506493502 2.4350649350649347e-05 117.66233766233765 9.3506493506493502 2.637987012987013e-05 121.03896103896103
		 9.3506493506493502 2.8409090909090906e-05 7.7922077922077913 -3.5064935064935057
		 3.2467532467532468e-05 10.909090909090908 -3.5064935064935057 3.4496753246753243e-05 23.896103896103895
		 -3.5064935064935057 3.8555194805194802e-05 31.948051948051948 -3.5064935064935057
		 4.0584415584415584e-05 35.714285714285708 -3.5064935064935057 4.261363636363636e-05 44.415584415584412
		 -3.5064935064935057 4.4642857142857136e-05 51.94805194805194 -3.5064935064935057
		 4.6672077922077919e-05 60.779220779220772 -3.5064935064935057 4.8701298701298694e-05 68.181818181818173
		 -3.5064935064935057 5.0730519480519477e-05 77.142857142857139 -3.5064935064935057
		 5.275974025974026e-05 84.545454545454533 -3.5064935064935057 5.4788961038961036e-05 7.9220779220779214
		 -16.36363636363636 5.8847402597402594e-05 10.779220779220779 -16.36363636363636 6.087662337662337e-05 23.766233766233764
		 -16.36363636363636 6.4935064935064935e-05 31.948051948051944 -16.36363636363636 6.6964285714285718e-05 35.584415584415581
		 -16.36363636363636 6.8993506493506487e-05 44.285714285714285 -16.36363636363636 7.1022727272727269e-05 52.467532467532465
		 -16.36363636363636 7.3051948051948052e-05 59.870129870129873 -16.36363636363636 7.5081168831168821e-05 68.831168831168824
		 -16.36363636363636 7.7110389610389604e-05 76.36363636363636 -16.36363636363636 7.9139610389610386e-05 84.415584415584405
		 -16.36363636363636 8.1168831168831169e-05 7.2727272727272734 -29.220779220779221
		 8.522727272727272e-05 10.519480519480519 -29.220779220779221 8.7256493506493503e-05 22.727272727272727
		 -29.220779220779221 9.1314935064935055e-05 31.688311688311686 -29.220779220779221
		 9.3344155844155837e-05 35.324675324675319 -29.220779220779221 9.537337662337662e-05 41.298701298701296
		 -29.220779220779221 9.7402597402597389e-05 51.558441558441551 -29.220779220779221
		 9.9431818181818172e-05 60.389610389610382 -29.220779220779221 0.00010146103896103895 68.571428571428569
		 -29.220779220779221 0.00010349025974025974 76.753246753246742 -29.220779220779221
		 0.00010551948051948052 84.935064935064929 -29.220779220779221 0.00010754870129870129 ;
	setAttr ".characterBoundingBoxesMin" -type "vectorArray" 46 1.1688311688311688
		 0 0 10.909090909090908 0 2.0292207792207792e-06 18.051948051948049 0 4.0584415584415584e-06 27.532467532467528
		 0 6.0876623376623368e-06 41.558441558441558 0 1.0146103896103896e-05 52.72727272727272
		 0 1.2175324675324674e-05 62.857142857142854 0 1.6233766233766234e-05 72.857142857142847
		 0 1.8262987012987013e-05 80.51948051948051 0 2.0292207792207792e-05 91.168831168831161
		 0 2.2321428571428568e-05 100.12987012987013 0 2.4350649350649347e-05 109.74025974025973
		 0 2.637987012987013e-05 119.74025974025973 0 2.8409090909090906e-05 0.12987012987012986
		 -12.857142857142856 3.2467532467532468e-05 9.6103896103896087 -12.857142857142856
		 3.4496753246753243e-05 17.142857142857142 -12.857142857142856 3.8555194805194802e-05 25.584415584415581
		 -12.857142857142856 4.0584415584415584e-05 34.15584415584415 -12.857142857142856
		 4.261363636363636e-05 37.662337662337656 -12.857142857142856 4.4642857142857136e-05 46.493506493506487
		 -12.857142857142856 4.6672077922077919e-05 54.15584415584415 -12.857142857142856
		 4.8701298701298694e-05 63.116883116883109 -12.857142857142856 5.0730519480519477e-05 70.389610389610382
		 -12.857142857142856 5.275974025974026e-05 79.480519480519476 -12.857142857142856
		 5.4788961038961036e-05 0.12987012987012986 -25.714285714285712 5.8847402597402594e-05 9.4805194805194795
		 -25.714285714285712 6.087662337662337e-05 17.532467532467532 -25.714285714285712
		 6.4935064935064935e-05 25.324675324675322 -25.714285714285712 6.6964285714285718e-05 34.025974025974023
		 -25.714285714285712 6.8993506493506487e-05 38.051948051948045 -25.714285714285712
		 7.1022727272727269e-05 46.103896103896098 -25.714285714285712 7.3051948051948052e-05 54.805194805194802
		 -25.714285714285712 7.5081168831168821e-05 62.857142857142854 -25.714285714285712
		 7.7110389610389604e-05 70.909090909090907 -25.714285714285712 7.9139610389610386e-05 78.831168831168824
		 -25.714285714285712 8.1168831168831169e-05 0.64935064935064934 -38.571428571428569
		 8.522727272727272e-05 9.2207792207792192 -38.571428571428569 8.7256493506493503e-05 17.662337662337659
		 -38.571428571428569 9.1314935064935055e-05 25.454545454545453 -38.571428571428569
		 9.3344155844155837e-05 33.766233766233761 -38.571428571428569 9.537337662337662e-05 38.571428571428569
		 -38.571428571428569 9.7402597402597389e-05 46.103896103896098 -38.571428571428569
		 9.9431818181818172e-05 54.025974025974023 -38.571428571428569 0.00010146103896103895 62.597402597402592
		 -38.571428571428569 0.00010349025974025974 70.779220779220779 -38.571428571428569
		 0.00010551948051948052 78.571428571428569 -38.571428571428569 0.00010754870129870129 ;
	setAttr ".manipulatorPivots" -type "vectorArray" 46 1.1688311688311688 0 0 10.909090909090908
		 0 2.0292207792207792e-06 18.051948051948049 0 4.0584415584415584e-06 27.532467532467528
		 -0.25974025974025972 6.0876623376623368e-06 41.558441558441558 0 1.0146103896103896e-05 52.72727272727272
		 0 1.2175324675324674e-05 62.857142857142854 0 1.6233766233766234e-05 72.857142857142847
		 0 1.8262987012987013e-05 80.51948051948051 -0.25974025974025972 2.0292207792207792e-05 91.168831168831161
		 -0.25974025974025972 2.2321428571428568e-05 100.12987012987013 0 2.4350649350649347e-05 109.74025974025973
		 0 2.637987012987013e-05 119.74025974025973 0 2.8409090909090906e-05 0.12987012987012986
		 -12.857142857142856 3.2467532467532468e-05 9.6103896103896087 -12.857142857142856
		 3.4496753246753243e-05 17.142857142857142 -12.857142857142856 3.8555194805194802e-05 25.584415584415581
		 -13.116883116883116 4.0584415584415584e-05 34.15584415584415 -12.857142857142856
		 4.261363636363636e-05 37.662337662337656 -12.857142857142856 4.4642857142857136e-05 46.493506493506487
		 -13.116883116883116 4.6672077922077919e-05 54.15584415584415 -13.116883116883116
		 4.8701298701298694e-05 63.116883116883109 -13.116883116883116 5.0730519480519477e-05 70.389610389610382
		 -12.857142857142856 5.275974025974026e-05 79.480519480519476 -13.116883116883116
		 5.4788961038961036e-05 0.12987012987012986 -25.714285714285712 5.8847402597402594e-05 9.4805194805194795
		 -25.714285714285712 6.087662337662337e-05 17.532467532467532 -25.97402597402597 6.4935064935064935e-05 25.324675324675322
		 -25.97402597402597 6.6964285714285718e-05 34.025974025974023 -25.714285714285712
		 6.8993506493506487e-05 38.051948051948045 -25.97402597402597 7.1022727272727269e-05 46.103896103896098
		 -25.97402597402597 7.3051948051948052e-05 54.805194805194802 -25.97402597402597 7.5081168831168821e-05 62.857142857142854
		 -25.714285714285712 7.7110389610389604e-05 70.909090909090907 -25.97402597402597
		 7.9139610389610386e-05 78.831168831168824 -25.714285714285712 8.1168831168831169e-05 0.64935064935064934
		 -38.571428571428569 8.522727272727272e-05 9.2207792207792192 -38.571428571428569
		 8.7256493506493503e-05 17.662337662337659 -38.831168831168824 9.1314935064935055e-05 25.454545454545453
		 -38.831168831168824 9.3344155844155837e-05 33.766233766233761 -38.571428571428569
		 9.537337662337662e-05 38.571428571428569 -38.571428571428569 9.7402597402597389e-05 46.103896103896098
		 -38.831168831168824 9.9431818181818172e-05 54.025974025974023 -38.831168831168824
		 0.00010146103896103895 62.597402597402592 -38.571428571428569 0.00010349025974025974 70.779220779220779
		 -38.571428571428569 0.00010551948051948052 78.571428571428569 -38.831168831168824
		 0.00010754870129870129 ;
	setAttr ".holeInfo" -type "Int32Array" 66 0 23 3651 1 15
		 3698 2 3 3721 6 3 3809 7 15 3836 8 32
		 3883 11 23 3994 17 3 4058 18 32 4110 20 3
		 4157 22 16 4257 24 3 4334 29 28 4456 29 33
		 4484 30 16 4549 32 28 4621 32 33 4649 33 32
		 4739 42 28 5075 42 33 5103 46 32 5268 49 32
		 5393 ;
	setAttr ".numberOfShells" 50;
	setAttr ".currentFont" -type "string" "Lucida Sans Unicode";
	setAttr ".currentStyle" -type "string" "Regular";
	setAttr ".manipulatorPositionsPP" -type "vectorArray" 164 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ;
	setAttr ".manipulatorWordPositionsPP" -type "vectorArray" 10 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ;
	setAttr ".manipulatorLinePositionsPP" -type "vectorArray" 5 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 ;
	setAttr ".manipulatorRotationsPP" -type "vectorArray" 164 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ;
	setAttr ".manipulatorWordRotationsPP" -type "vectorArray" 10 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ;
	setAttr ".manipulatorLineRotationsPP" -type "vectorArray" 5 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 ;
	setAttr ".manipulatorScalesPP" -type "vectorArray" 164 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ;
	setAttr ".manipulatorWordScalesPP" -type "vectorArray" 10 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ;
	setAttr ".manipulatorLineScalesPP" -type "vectorArray" 5 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 ;
	setAttr ".alignmentAdjustments" -type "doubleArray" 5 0 0 0 0 0 ;
	setAttr ".manipulatorMode" 0;
	setAttr ".legacyDecomposition" yes;
	setAttr ".preTLDecompose" yes;
createNode vectorExtrude -name "typeExtrude1";
	rename -uuid "7B462C39-490B-3E5E-2F2D-52BE68B45E6A";
	addAttr -storable false -cachedInternally true -hidden true -shortName "typeMessage" 
		-longName "typeMessage" -attributeType "message";
	setAttr ".solidsPerCharacter" -type "doubleArray" 0 ;
	setAttr ".solidsPerWord" -type "doubleArray" 0 ;
	setAttr ".solidsPerLine" -type "doubleArray" 0 ;
	setAttr ".capComponents" -type "componentList" 1 "f[0:99]";
	setAttr ".extrusionComponents" -type "componentList" 1 "f[89:1900]";
	setAttr ".extrudeDivisions" 1;
	setAttr ".extrudeDistancePP" -type "doubleArray" 0 ;
	setAttr ".extrudeDistanceScalePP" -type "doubleArray" 0 ;
	setAttr -size 4 ".frontBevelCurve[0:3]"  0 1 0.5 1 1 0.5 1 0;
	setAttr -size 4 ".backBevelCurve[0:3]"  0 1 0.5 1 1 0.5 1 0;
	setAttr -size 4 ".extrudeCurve[0:3]"  0 0.5 0.333 0.5 0.667 0.5 1
		 0.5;
	setAttr -size 4 ".outerBevelCurve[0:3]"  0 1 0.5 1 1 0.5 1 0;
createNode groupId -name "groupid1";
	rename -uuid "F05F7016-483B-EE44-A638-49AD066F2753";
createNode groupId -name "groupid2";
	rename -uuid "AD6889FC-4F5F-4077-8995-F7963350DEA0";
createNode groupId -name "groupid3";
	rename -uuid "3C291A5F-4CE7-17FA-161F-4DAE4A6A1487";
createNode blinn -name "typeBlinn";
	rename -uuid "5AA87111-4FEA-7C78-2D30-8AB33FA0E813";
	setAttr ".color" -type "float3" 1 1 1 ;
createNode shadingEngine -name "typeBlinnSG";
	rename -uuid "50925500-438F-C384-2D15-5BB1EE4B596B";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".renderableOnlySet" yes;
createNode materialInfo -name "materialInfo1";
	rename -uuid "EC7693B9-4F52-B590-9148-0C93DEBF0BE6";
createNode vectorAdjust -name "vectorAdjust1";
	rename -uuid "78BA8E50-4337-2269-FEED-509BE76E128B";
	setAttr ".extrudeDistanceScalePP" -type "doubleArray" 0 ;
	setAttr ".boundingBoxes" -type "vectorArray" 34 0.90909093618392944 3.5064935684204102
		 0 0.90909093618964376 3.5064935684211895 2.4999999999999998e-12 9.4805192947387695
		 0 2.0292209228500724e-06 9.4805192947414962 9.3506488800048831e-12 2.029223422850189e-06 17.662338256835938
		 0 4.0584418457001448e-06 17.662338256838666 9.3506488800048831e-12 4.0584443457001399e-06 25.064935684204102
		 -0.25974026322364807 6.0876623138028663e-06 25.064935684210337 -0.25974026321377797
		 6.0876648138029774e-06 33.376625061035156 0 8.1168836914002895e-06 33.376625061036712
		 1.5584415197372435e-12 8.1168861914002795e-06 36.88311767578125 0 1.014610370475566e-05 36.883117675788
		 9.3506488800048831e-12 1.0146106204755765e-05 45.454544067382813 0 1.2175324627605733e-05 45.454544067388397
		 9.6103897094726559e-12 1.2175327127605716e-05 1.4285714626312256 -12.857142448425293
		 1.6233767382800579e-05 1.4285714626371997 -12.857142448415942 1.6233769882800559e-05 9.740260124206543
		 -13.116883277893066 1.8262986486661248e-05 9.7402601242116074 -13.116883277883456
		 1.8262988986661343e-05 17.662338256835938 -12.857142448425293 2.029220740951132e-05 17.662338256837497
		 -12.857142448423735 2.0292209909511293e-05 21.948051452636719 -12.857142448425293
		 2.2321428332361393e-05 21.948051452642694 -12.857142448415942 2.2321430832361481e-05 29.740259170532227
		 -12.857142448425293 2.4350649255211465e-05 29.740259170537811 -12.857142448415683
		 2.4350651755211435e-05 0.90909093618392944 -25.974025726318359 2.840909110091161e-05 0.90909093619029313
		 -25.97402572630849 2.8409093600911573e-05 9.6103897094726563 -25.714284896850586
		 3.0438310204772279e-05 9.6103897094786301 -25.714284896841235 3.0438312704772357e-05 17.662338256835938
		 -25.714284896850586 3.2467534765601158e-05 17.662338256837497 -25.714284896849026
		 3.2467537265601114e-05 21.558441162109375 -25.714284896850586 3.4496755688451231e-05 21.55844116211496
		 -25.714284896840976 3.4496758188451302e-05 30.649351119995117 -25.714284896850586
		 3.6525972973322496e-05 30.649351119997846 -25.714284896841235 3.6525975473322445e-05 ;
createNode tweak -name "tweak1";
	rename -uuid "BE3546E2-4F47-56D2-071C-F599FA62C5E5";
createNode objectSet -name "vectorAdjust1Set";
	rename -uuid "FC970E34-4D0C-746D-12F4-E88E4C3AB1FF";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".verticesOnlySet" yes;
createNode groupId -name "vectorAdjust1GroupId";
	rename -uuid "3B995A42-461F-9290-D438-A799B2EEFEE9";
	setAttr ".isHistoricallyInteresting" 0;
createNode groupParts -name "vectorAdjust1GroupParts";
	rename -uuid "AB8280C9-45C6-C6EE-2873-1DA7E07743D5";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".inputComponents" -type "componentList" 1 "vtx[*]";
createNode objectSet -name "tweakSet1";
	rename -uuid "3A00D8A3-44B2-38D8-7D08-109E5176BAA9";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".verticesOnlySet" yes;
createNode groupId -name "groupId2";
	rename -uuid "72EF9E0A-459C-320E-7FDE-8F94A75641B7";
	setAttr ".isHistoricallyInteresting" 0;
createNode groupParts -name "groupParts2";
	rename -uuid "B706CB3B-4EDD-BB5B-7788-A0BEC605528E";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".inputComponents" -type "componentList" 1 "vtx[*]";
createNode groupId -name "groupId3";
	rename -uuid "8C84345F-4290-AAF6-BBB2-C19999AB561D";
createNode groupId -name "groupId4";
	rename -uuid "B1BC16F3-4B99-7708-F5EC-CE8976D2FD84";
createNode groupId -name "groupId5";
	rename -uuid "D9C46E0B-4954-9F44-94D5-A2A384FF95BD";
createNode groupId -name "groupId6";
	rename -uuid "CBD88963-4C06-EE47-8A5C-648A6C4D911E";
createNode groupId -name "groupId7";
	rename -uuid "808B0695-4E58-5F8F-CF5A-F18B22353FAE";
createNode groupId -name "groupId8";
	rename -uuid "8C361045-4490-6058-A416-EDB3EE97C11A";
createNode polyRemesh -name "polyRemesh1";
	rename -uuid "D77EC88F-4D85-F76C-D9EC-D78A4D15EBEB";
	addAttr -storable false -cachedInternally true -hidden true -shortName "typeMessage" 
		-longName "typeMessage" -attributeType "message";
	setAttr ".nodeState" 1;
	setAttr ".inputMatrix" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".tessellateBorders" no;
	setAttr ".interpolationType" 0;
createNode polyAutoProj -name "polyAutoProj1";
	rename -uuid "A822BC84-4177-1A94-45B1-E2A7705C6DA0";
	setAttr ".useOldPolyArchitecture" yes;
	setAttr ".inputComponents" -type "componentList" 1 "f[*]";
	setAttr ".inputMatrix" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".percentageSpace" 0.20000000298023224;
	setAttr ".denseLayout" yes;
createNode shellDeformer -name "shellDeformer1";
	rename -uuid "5B1192CF-49D6-40EB-708C-EA92D62066E8";
	addAttr -storable false -cachedInternally true -hidden true -shortName "typeMessage" 
		-longName "typeMessage" -attributeType "message";
	setAttr ".positionInPP" -type "vectorArray" 0 ;
	setAttr ".scaleInPP" -type "vectorArray" 0 ;
	setAttr ".rotationInPP" -type "vectorArray" 0 ;
createNode tweak -name "tweak2";
	rename -uuid "9A9246AB-40AE-18A6-334B-BAB59403F29E";
createNode objectSet -name "shellDeformer1Set";
	rename -uuid "2B5F2E71-44B0-403E-A30E-FEA4A2F7B6D5";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".verticesOnlySet" yes;
createNode groupId -name "shellDeformer1GroupId";
	rename -uuid "8B0795A1-447F-60B7-D0FA-D8AC508BED21";
	setAttr ".isHistoricallyInteresting" 0;
createNode groupParts -name "shellDeformer1GroupParts";
	rename -uuid "92D81CDD-4E27-75AD-E914-0CAFA46D3D33";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".inputComponents" -type "componentList" 1 "vtx[*]";
createNode objectSet -name "tweakSet2";
	rename -uuid "801AD061-4511-DB9C-8F1D-DDA377659852";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".verticesOnlySet" yes;
createNode groupId -name "groupId10";
	rename -uuid "D7AC6E72-47A1-D8B4-1134-5A9AE432DE5F";
	setAttr ".isHistoricallyInteresting" 0;
createNode groupParts -name "groupParts4";
	rename -uuid "C838ADC6-46C7-F063-3BC1-039D20A8CFF3";
	setAttr ".isHistoricallyInteresting" 0;
	setAttr ".inputComponents" -type "componentList" 1 "vtx[*]";
createNode script -name "sceneConfigurationScriptNode";
	rename -uuid "95D74CF0-484F-A9EC-0C4D-F480936C3CA6";
	setAttr ".before" -type "string" "playbackOptions -min 0 -max 100 -ast 0 -aet 100 ";
	setAttr ".scriptType" 6;
createNode groupId -name "groupId11";
	rename -uuid "63E93977-435F-83A7-1822-7E83FDEA9BDD";
createNode groupId -name "groupId12";
	rename -uuid "70EAFAB4-4872-103D-A4C7-26815E2757E8";
createNode groupId -name "groupId13";
	rename -uuid "9DEEBADE-4103-0ACB-B620-62991075CDAC";
createNode groupId -name "groupId14";
	rename -uuid "47AEE563-4B5D-3263-DD3F-88BB8F424E83";
createNode groupId -name "groupId15";
	rename -uuid "76525E5A-4977-00F8-1907-4997C38CC440";
createNode groupId -name "groupId16";
	rename -uuid "9B24E5BD-4B26-46CD-EB2A-BABBE0060B3E";
createNode groupId -name "groupId17";
	rename -uuid "6DF40E39-4A32-F1B2-E640-3EBEE3101B95";
createNode groupId -name "groupId18";
	rename -uuid "EE022B59-4DB9-74E4-A368-FEA0FD746F94";
createNode groupId -name "groupId19";
	rename -uuid "6E7554D3-4958-2618-A200-99BE8C638796";
createNode groupId -name "groupId20";
	rename -uuid "85992181-467A-51EB-7700-138DD50E5BF6";
createNode groupId -name "groupId21";
	rename -uuid "DE6E10C7-46F1-8B3D-643F-2C8F5EC080B4";
createNode groupId -name "groupId22";
	rename -uuid "DB71D6FF-4704-A294-ECF5-0D858BAFCA25";
createNode groupId -name "groupId23";
	rename -uuid "8CFD446B-4E26-7ECD-C2C0-0EB74F6301F8";
createNode groupId -name "groupId24";
	rename -uuid "25D7615D-45ED-39FF-A808-24ABF97B7E92";
createNode groupId -name "groupId25";
	rename -uuid "EFD58366-4183-4D50-CAB5-7BB0A2B3BBFA";
createNode groupId -name "groupId26";
	rename -uuid "C372E9E7-4666-47AA-B3DF-A09E2688AFC7";
createNode groupId -name "groupId27";
	rename -uuid "B93D180D-43E1-A658-FC78-2A95085CA5BE";
createNode groupId -name "groupId28";
	rename -uuid "12486926-4B22-A428-1D58-F7BB1DAEF076";
createNode groupId -name "groupId29";
	rename -uuid "FE88B5C8-4BE1-EC2F-ED31-AC8DC870D23C";
createNode groupId -name "groupId30";
	rename -uuid "0F29A274-4E39-FC2C-62CA-8E83C3847CBE";
createNode groupId -name "groupId31";
	rename -uuid "046630E1-44CA-CA60-E81C-42A9D3A8C180";
createNode groupId -name "groupId32";
	rename -uuid "09C3949E-4D69-F3F8-08EA-AA93C43BB209";
createNode groupId -name "groupId33";
	rename -uuid "2DC0F7E6-40EC-D990-E2E0-1FBF6461A5DE";
createNode groupId -name "groupId34";
	rename -uuid "8DA2B290-4C07-FA10-9752-F0A02EDAD05C";
createNode groupId -name "groupId35";
	rename -uuid "02A985A2-465D-F103-2F69-438653E17476";
createNode groupId -name "groupId36";
	rename -uuid "FCB2D82E-4A1B-9F9B-59BE-ABA1A779EA2B";
createNode groupId -name "groupId37";
	rename -uuid "CC29308A-44AD-F58B-2E0C-0D8934599238";
createNode groupId -name "groupId38";
	rename -uuid "61E2595E-4B22-9A01-6A4A-C48D06C094B3";
createNode groupId -name "groupId39";
	rename -uuid "3A02C2E3-4240-FF89-D19B-068075B6060C";
createNode groupId -name "groupId40";
	rename -uuid "B275C617-4800-C96F-BF4D-EDAA41EFFE39";
createNode groupId -name "groupId41";
	rename -uuid "F83D0C9F-48EE-469D-5325-D3B67EF79A96";
createNode groupId -name "groupId42";
	rename -uuid "CFCE57D5-48B4-3754-8636-B3947041139B";
createNode groupId -name "groupId43";
	rename -uuid "5BF8E0E0-45BD-E4AC-723C-66A77762D32E";
createNode groupId -name "groupId44";
	rename -uuid "FC25EC9B-4BAF-0F39-23F9-2DB3878C660A";
createNode groupId -name "groupId45";
	rename -uuid "BB4A637C-4E5C-A5AD-7D1D-B48F71A29AD2";
createNode groupId -name "groupId46";
	rename -uuid "E59107A5-44DF-6F5B-20A4-0F96E1C96A3A";
createNode groupId -name "groupId47";
	rename -uuid "30AD3D2A-416C-A504-CA07-C7A676D9922E";
createNode groupId -name "groupId48";
	rename -uuid "A0342C26-45ED-9C1F-AD6E-3FAC1AC213FE";
createNode groupId -name "groupId49";
	rename -uuid "46ADEAD3-4A3B-39D3-EE94-21A89855EBFA";
createNode groupId -name "groupId50";
	rename -uuid "02D7FD2C-4265-08EC-8755-2BA5FB2B4420";
createNode groupId -name "groupId51";
	rename -uuid "382AC9E6-4672-097F-0D49-8B9296B25212";
createNode groupId -name "groupId52";
	rename -uuid "1EE46B5D-4226-A8F4-CB26-52B4F74EEEBF";
createNode groupId -name "groupId53";
	rename -uuid "4524C819-4302-A79C-30A3-EABF3B264D21";
createNode groupId -name "groupId54";
	rename -uuid "2AFC22DA-46A7-2483-6F0B-95BFA5008659";
createNode groupId -name "groupId55";
	rename -uuid "60321FA8-44B4-FE41-4E13-02BF6029D48A";
createNode groupId -name "groupId56";
	rename -uuid "E5C430E1-4DB5-977E-6116-14B38564B335";
createNode groupId -name "groupId57";
	rename -uuid "5B6582A8-4FA0-9DA2-5FB7-908A03A7DE98";
createNode groupId -name "groupId58";
	rename -uuid "D1763403-459D-BA13-C947-4F97DFF18503";
createNode groupId -name "groupId59";
	rename -uuid "FDBBEA76-49EE-1DE2-07F5-5593A9038CA1";
createNode groupId -name "groupId60";
	rename -uuid "F6FA5475-4165-CD5F-5AE8-3D8657FA1DA3";
createNode groupId -name "groupId61";
	rename -uuid "C292A874-4061-AF6B-91C7-2C926401AF01";
createNode groupId -name "groupId62";
	rename -uuid "1A67420C-4809-9554-07D7-4A8D866F6ABF";
createNode groupId -name "groupId63";
	rename -uuid "BAC08584-4B79-2CDD-7D45-A3B608AF75F3";
createNode groupId -name "groupId64";
	rename -uuid "613329C6-47EE-EDC4-7737-AA9B608C86E8";
createNode groupId -name "groupId65";
	rename -uuid "5BDBEEB5-476D-DAA9-625B-4BB307B043EC";
createNode groupId -name "groupId66";
	rename -uuid "DF84CD35-4A29-07EB-7DC8-DB8F0748C7EA";
createNode groupId -name "groupId67";
	rename -uuid "C118A6D7-4115-0330-A793-C89BD93003D3";
createNode groupId -name "groupId68";
	rename -uuid "54ECCD54-41F9-9B79-0045-E687EA16C20C";
createNode groupId -name "groupId69";
	rename -uuid "3725EB14-48EB-98C3-318C-A4B1DDBB9D87";
createNode groupId -name "groupId70";
	rename -uuid "DF52B0BC-4DFA-462B-6323-EA937E5067A5";
createNode groupId -name "groupId71";
	rename -uuid "977B7639-4121-CF31-0099-8EB2CA80D64B";
createNode groupId -name "groupId72";
	rename -uuid "69DB3D3F-459D-7261-AB58-86A6FCC336C4";
createNode groupId -name "groupId73";
	rename -uuid "8B37E69C-45E0-30FA-B329-41B6AACD5E59";
createNode groupId -name "groupId74";
	rename -uuid "8EEBAC38-45CA-626C-2CDC-7298799C496D";
createNode groupId -name "groupId75";
	rename -uuid "5D60EAC6-4492-046C-F1F6-F0A7AC17DE76";
createNode groupId -name "groupId76";
	rename -uuid "3E7C1DD3-43F0-F6BD-77EB-359564E14FFE";
createNode groupId -name "groupId77";
	rename -uuid "958A66EC-4666-525F-DF5F-A29CD7F2862F";
createNode groupId -name "groupId78";
	rename -uuid "71ADF1CD-446C-3CB0-7A56-039F748D7E05";
createNode groupId -name "groupId79";
	rename -uuid "C5A705B2-48E5-4111-D8A0-2AB79B7473C6";
createNode groupId -name "groupId80";
	rename -uuid "235C3FBF-47C6-5FF7-6678-279089972654";
createNode groupId -name "groupId81";
	rename -uuid "4E3F6798-44CA-FF72-CABD-A4AD2D2AA3A7";
createNode groupId -name "groupId82";
	rename -uuid "2D4AD942-49F4-8F25-C03B-AA8FAF7256EC";
createNode groupId -name "groupId83";
	rename -uuid "B815DE12-46C9-676B-7B10-45B6391D4CAD";
createNode groupId -name "groupId84";
	rename -uuid "2B2957FA-4933-5913-4A77-05A0722E8D79";
createNode groupId -name "groupId85";
	rename -uuid "BD5D0E4F-459C-CD88-E47F-8E8AE8BE402D";
createNode groupId -name "groupId86";
	rename -uuid "B4EB27E4-427B-D955-BEEC-0BB9F4EF49B6";
createNode groupId -name "groupId87";
	rename -uuid "3FAF66DE-4A09-881D-D8DD-4989F871CCF6";
createNode groupId -name "groupId88";
	rename -uuid "E3346B17-497A-0609-3EC9-82A670CCD88B";
createNode groupId -name "groupId89";
	rename -uuid "1E698FDB-4DE2-140A-404C-EFB8514F06F6";
createNode groupId -name "groupId90";
	rename -uuid "CFC79C97-4A46-D9A6-4D39-D8A7340DA7EB";
createNode groupId -name "groupId91";
	rename -uuid "04992793-4628-9CA6-D73C-5FBB11C4238B";
createNode groupId -name "groupId92";
	rename -uuid "EE91B322-4948-5B98-C071-B28B2DE007F4";
createNode groupId -name "groupId93";
	rename -uuid "8B6237DC-4C89-3F3E-0AD9-E8B4015AEB06";
createNode groupId -name "groupId94";
	rename -uuid "141439FE-490F-FA46-584B-45BA78D4A001";
createNode groupId -name "groupId95";
	rename -uuid "6E69B66F-4A8B-45A4-34F0-29A89979C89C";
createNode groupId -name "groupId96";
	rename -uuid "02DC486E-40F9-1023-5BEE-CAB608437641";
createNode groupId -name "groupId97";
	rename -uuid "BED93756-467E-64DF-C192-EB99374A7E84";
createNode groupId -name "groupId98";
	rename -uuid "843956D1-42A2-DCF2-4D13-4B98CFE25CC6";
createNode groupId -name "groupId99";
	rename -uuid "A918DE63-4547-A621-4072-80906E2DF482";
createNode groupId -name "groupId100";
	rename -uuid "6CABDD2D-4996-9830-D85B-E5B5CFDA2997";
createNode groupId -name "groupId101";
	rename -uuid "91B6B7CF-4E95-C371-330E-3F9ABB0CA56E";
createNode groupId -name "groupId102";
	rename -uuid "7F504E28-4722-89BD-09C7-9E8F3E8E5DBF";
createNode groupId -name "groupId103";
	rename -uuid "031ACEAA-488B-27A4-FDDC-A8BF2BDA64A6";
createNode groupId -name "groupId104";
	rename -uuid "873F4CD1-4BDF-6318-373D-B3A886542431";
createNode groupId -name "groupId105";
	rename -uuid "923FF385-49CE-7654-6350-02A344FC2B35";
createNode groupId -name "groupId106";
	rename -uuid "E39F024F-4F17-7AF5-D738-F58F6870B8E1";
createNode groupId -name "groupId107";
	rename -uuid "53B66128-4B58-3D57-2959-C4B435C0B24A";
createNode groupId -name "groupId108";
	rename -uuid "E6ACE279-44BD-AA35-1355-A9ACB56A058B";
createNode groupId -name "groupId109";
	rename -uuid "68FA44BB-4575-B447-DD1E-688B9C06AE44";
createNode groupId -name "groupId110";
	rename -uuid "C4D702BC-453B-64DE-22F5-48B5ED952949";
createNode groupId -name "groupId111";
	rename -uuid "DF54DA65-418F-8193-A79A-D5A871828AA1";
createNode groupId -name "groupId112";
	rename -uuid "E292A609-4E7D-611F-5AA3-7A895E85F57A";
createNode groupId -name "groupId113";
	rename -uuid "D44425A5-41C8-8BAC-E8F8-939DD3BC25E2";
createNode groupId -name "groupId114";
	rename -uuid "5076D469-4CFE-F582-8FA6-D0AEE667A112";
createNode groupId -name "groupId115";
	rename -uuid "7DA93B20-4D01-7182-3287-57946282433E";
createNode groupId -name "groupId116";
	rename -uuid "AF32A2BE-4E29-BA78-39AF-1AA258F48171";
createNode groupId -name "groupId117";
	rename -uuid "03A31211-4FDC-A2B3-8CCC-DE8D5E0E6BA8";
createNode groupId -name "groupId118";
	rename -uuid "38F6AD9A-49D0-68F1-8CD8-0B81F84E091E";
createNode groupId -name "groupId119";
	rename -uuid "97392C62-42E4-1E3D-32D0-A3A9FA803926";
createNode groupId -name "groupId120";
	rename -uuid "6DDE3883-4EE0-2F90-27D5-88B577855895";
createNode groupId -name "groupId121";
	rename -uuid "CD6A0166-4147-E6E6-5780-56B7EA22D2A3";
createNode groupId -name "groupId122";
	rename -uuid "B3B11EB5-4BFA-398B-EF9F-B4B28FE580A0";
createNode groupId -name "groupId123";
	rename -uuid "910A187A-489B-A181-5EF7-0295C8CC8EEB";
createNode groupId -name "groupId124";
	rename -uuid "0F27BEEB-44F8-CBC3-0177-CD9B0265AEF2";
createNode groupId -name "groupId125";
	rename -uuid "2277FA25-48AC-BAFF-3E72-7599FE04E388";
createNode groupId -name "groupId126";
	rename -uuid "C5512FB1-460E-E152-CF12-CB8F94FA85FF";
createNode groupId -name "groupId127";
	rename -uuid "D74CBF12-4C9A-E4C3-C6F6-79B7FE355450";
createNode groupId -name "groupId128";
	rename -uuid "A3DA4F7E-49EC-EF93-05B1-889022A7A7E2";
createNode groupId -name "groupId129";
	rename -uuid "8E3BC2BD-41E4-5650-9D6F-6EA73013EFD9";
createNode groupId -name "groupId130";
	rename -uuid "5F5322F7-4D97-138E-943A-EFB39CC99C5A";
createNode groupId -name "groupId131";
	rename -uuid "C9CE8EFD-4739-DA7F-1FD7-50B95B3A3B5B";
createNode groupId -name "groupId132";
	rename -uuid "910D08B7-4122-4808-43DF-0AA5A7DE095B";
createNode groupId -name "groupId133";
	rename -uuid "0A538D3D-408A-A2F4-7197-AB8A4F546626";
createNode groupId -name "groupId134";
	rename -uuid "F75B3C81-4A28-AF2D-2390-75A42FDC773A";
createNode groupId -name "groupId135";
	rename -uuid "FBA70A4B-4E74-5A3D-C5F5-D7B4ABD4FDFF";
createNode groupId -name "groupId136";
	rename -uuid "54A3FE25-482E-DF4B-C364-4D9CB829B043";
createNode groupId -name "groupId137";
	rename -uuid "F13DF1F7-434F-290C-44E6-D8BF632B26EF";
createNode groupId -name "groupId138";
	rename -uuid "964C3813-4AA2-9CE3-5008-809A7E9463BF";
createNode groupId -name "groupId139";
	rename -uuid "A15CCE40-4B5B-CB22-AC30-65AB17530DBF";
createNode groupId -name "groupId140";
	rename -uuid "15FE1AF3-4349-1B47-9ACA-EEB74F6E2BF0";
createNode groupId -name "groupId141";
	rename -uuid "7B8A9151-4DBA-94D6-C11F-229F5FCAD2CB";
createNode groupId -name "groupId142";
	rename -uuid "2FA08686-4B34-F2CC-4124-DD88DFC1DEA5";
createNode groupId -name "groupId143";
	rename -uuid "EFC36D7E-4067-36E7-8966-B5B0E4B20607";
createNode groupId -name "groupId144";
	rename -uuid "3DAD6579-4B53-1F12-F2CE-FBBA52EE5CA0";
createNode nodeGraphEditorInfo -name "MayaNodeEditorSavedTabsInfo";
	rename -uuid "92DFE1F2-4CB1-3B9E-E86C-F9995A251972";
	setAttr ".tabGraphInfo[0].tabName" -type "string" "Untitled_1";
	setAttr ".tabGraphInfo[0].viewRectLow" -type "double2" -1468.5041017002268 -303.58741728370035 ;
	setAttr ".tabGraphInfo[0].viewRectHigh" -type "double2" 26.465496160295256 524.20566582915058 ;
	setAttr -size 18 ".tabGraphInfo[0].nodeInfo";
	setAttr ".tabGraphInfo[0].nodeInfo[0].positionX" -717.14288330078125;
	setAttr ".tabGraphInfo[0].nodeInfo[0].positionY" 192.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[0].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[1].positionX" 818.5714111328125;
	setAttr ".tabGraphInfo[0].nodeInfo[1].positionY" 27.142856597900391;
	setAttr ".tabGraphInfo[0].nodeInfo[1].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[2].positionX" 1125.7142333984375;
	setAttr ".tabGraphInfo[0].nodeInfo[2].positionY" -305.71429443359375;
	setAttr ".tabGraphInfo[0].nodeInfo[2].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[3].positionX" -102.85713958740234;
	setAttr ".tabGraphInfo[0].nodeInfo[3].positionY" 180;
	setAttr ".tabGraphInfo[0].nodeInfo[3].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[4].positionX" 818.5714111328125;
	setAttr ".tabGraphInfo[0].nodeInfo[4].positionY" 128.57142639160156;
	setAttr ".tabGraphInfo[0].nodeInfo[4].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[5].positionX" -1024.2857666015625;
	setAttr ".tabGraphInfo[0].nodeInfo[5].positionY" 164.28572082519531;
	setAttr ".tabGraphInfo[0].nodeInfo[5].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[6].positionX" 1125.7142333984375;
	setAttr ".tabGraphInfo[0].nodeInfo[6].positionY" 385.71429443359375;
	setAttr ".tabGraphInfo[0].nodeInfo[6].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[7].positionX" -410;
	setAttr ".tabGraphInfo[0].nodeInfo[7].positionY" 154.28572082519531;
	setAttr ".tabGraphInfo[0].nodeInfo[7].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[8].positionX" 818.5714111328125;
	setAttr ".tabGraphInfo[0].nodeInfo[8].positionY" -175.71427917480469;
	setAttr ".tabGraphInfo[0].nodeInfo[8].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[9].positionX" 204.28572082519531;
	setAttr ".tabGraphInfo[0].nodeInfo[9].positionY" 290;
	setAttr ".tabGraphInfo[0].nodeInfo[9].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[10].positionX" -102.85713958740234;
	setAttr ".tabGraphInfo[0].nodeInfo[10].positionY" 78.571426391601563;
	setAttr ".tabGraphInfo[0].nodeInfo[10].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[11].positionX" -1331.4285888671875;
	setAttr ".tabGraphInfo[0].nodeInfo[11].positionY" 192.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[11].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[12].positionX" 818.5714111328125;
	setAttr ".tabGraphInfo[0].nodeInfo[12].positionY" -74.285713195800781;
	setAttr ".tabGraphInfo[0].nodeInfo[12].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[13].positionX" 818.5714111328125;
	setAttr ".tabGraphInfo[0].nodeInfo[13].positionY" 230;
	setAttr ".tabGraphInfo[0].nodeInfo[13].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[14].positionX" 511.42855834960938;
	setAttr ".tabGraphInfo[0].nodeInfo[14].positionY" 271.42855834960938;
	setAttr ".tabGraphInfo[0].nodeInfo[14].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[15].positionX" -410;
	setAttr ".tabGraphInfo[0].nodeInfo[15].positionY" 312.85714721679688;
	setAttr ".tabGraphInfo[0].nodeInfo[15].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[16].positionX" 204.28572082519531;
	setAttr ".tabGraphInfo[0].nodeInfo[16].positionY" 81.428573608398438;
	setAttr ".tabGraphInfo[0].nodeInfo[16].nodeVisualState" 18304;
	setAttr ".tabGraphInfo[0].nodeInfo[17].positionX" 1125.7142333984375;
	setAttr ".tabGraphInfo[0].nodeInfo[17].positionY" 230;
	setAttr ".tabGraphInfo[0].nodeInfo[17].nodeVisualState" 18304;
createNode mPyNode -name "textMeshGeneratorNode";
	rename -uuid "5B6AA15B-4C62-1631-AE75-B9A252FACCFC";
	addAttr -writable false -storable false -keyable true -shortName "output" -longName "output" 
		-dataType "string";
	addAttr -readable false -cachedInternally true -keyable true -shortName "decimals" 
		-longName "decimals" -minValue 0 -attributeType "long";
	addAttr -readable false -cachedInternally true -shortName "inPosition" -longName "inPosition" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -readable false -cachedInternally true -shortName "inPositionX" -longName "inPositionX" 
		-attributeType "double" -parent "inPosition";
	addAttr -readable false -cachedInternally true -shortName "inPositionY" -longName "inPositionY" 
		-attributeType "double" -parent "inPosition";
	addAttr -readable false -cachedInternally true -shortName "inPositionZ" -longName "inPositionZ" 
		-attributeType "double" -parent "inPosition";
	setAttr ".expression" -type "string" "# Name: Text Mesh Generator\n# Author: Eric Vignola - eric.vignola@gmail.com\n# \n# Demonstrates: - How to output a hex string expected by a \"type\" node\n#\n# Explanation: Given an input position and a number of decimals the code will\n#              give a properly formatted string a \"type\" node can then convert as a mesh.\n#\n# For fun: - Select mesh and drag it around to see the effect.\n#          - Change the decimal count. weeeeeee!\n\n\n# Convert XYZ input as strings rounded \noutput = 'DRAG ME AROUND!\\n'\noutput += 'X: %s\\n'%round(inPosition[0],decimals)\noutput += 'Y: %s\\n'%round(inPosition[1],decimals)\noutput += 'Z: %s\\n'%round(inPosition[2],decimals)\n\n\n# These two steps are important to convert unicode --> hex which is what type1.textInput expects\noutput = output.encode(\"hex\") \noutput = ' '.join([i+j for i,j in zip(output[::2],output[1::2])])\n";
	setAttr "._inputAttrs" -type "string" "gAJ9cQEoWAgAAABkZWNpbWFsc11xAlgDAAAAaW50cQNhWAoAAABpblBvc2l0aW9ucQRdcQVYBgAA\nAHZlY3RvcnEGYXUu\n";
	setAttr "._outputAttrs" -type "string" "(dp1\nS'output'\np2\n(lp3\nS'string'\np4\nas.";
	setAttr "._storedVarsData" -type "string" "gAJ9cQEu\n";
	setAttr -keyable on ".decimals" 6;
createNode animCurveTL -name "typeMesh1_translateX";
	rename -uuid "30C0AB86-4638-8DA8-4172-FF84E43FFEF5";
	setAttr ".tangentType" 18;
	setAttr -size 5 ".keyTimeValue[0:4]"  0 0 21 -118.42387358691352 50 -22.712097475410886
		 74 24.806587636120657 100 0;
createNode animCurveTL -name "typeMesh1_translateY";
	rename -uuid "AF96D569-45AD-9040-993D-E6A0B544DBB0";
	setAttr ".tangentType" 18;
	setAttr -size 5 ".keyTimeValue[0:4]"  0 0 21 75.716343638008496 50 86.543921737773019
		 74 -38.61253062059658 100 0;
createNode animCurveTL -name "typeMesh1_translateZ";
	rename -uuid "5CAD6264-42CE-9F2F-9C33-EAA1EC961281";
	setAttr ".tangentType" 18;
	setAttr -size 5 ".keyTimeValue[0:4]"  0 0 21 67.205950163014251 50 -72.101596598272891
		 74 60.835466097289377 100 0;
createNode script -name "uiConfigurationScriptNode";
	rename -uuid "9F4B36EB-4898-3695-B23B-FB822BC1B678";
	setAttr ".before" -type "string" (
		"// Maya Mel UI Configuration File.\n//\n//  This script is machine generated.  Edit at your own risk.\n//\n//\n\nglobal string $gMainPane;\nif (`paneLayout -exists $gMainPane`) {\n\n\tglobal int $gUseScenePanelConfig;\n\tint    $useSceneConfig = $gUseScenePanelConfig;\n\tint    $nodeEditorPanelVisible = stringArrayContains(\"nodeEditorPanel1\", `getPanel -vis`);\n\tint    $nodeEditorWorkspaceControlOpen = (`workspaceControl -exists nodeEditorPanel1Window` && `workspaceControl -q -visible nodeEditorPanel1Window`);\n\tint    $menusOkayInPanels = `optionVar -q allowMenusInPanels`;\n\tint    $nVisPanes = `paneLayout -q -nvp $gMainPane`;\n\tint    $nPanes = 0;\n\tstring $editorName;\n\tstring $panelName;\n\tstring $itemFilterName;\n\tstring $panelConfig;\n\n\t//\n\t//  get current state of the UI\n\t//\n\tsceneUIReplacement -update $gMainPane;\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Top View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Top View\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"top\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n"
		+ "            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n"
		+ "            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1\n            -height 1\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n"
		+ "\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Side View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Side View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"side\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n"
		+ "            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n"
		+ "            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1\n            -height 1\n"
		+ "            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Front View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Front View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"front\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n"
		+ "            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n"
		+ "            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n"
		+ "            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1\n            -height 1\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Persp View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Persp View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"persp\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n"
		+ "            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n"
		+ "            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n"
		+ "            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 642\n            -height 1301\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"outlinerPanel\" (localizedPanelLabel(\"ToggledOutliner\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\toutlinerPanel -edit -l (localizedPanelLabel(\"ToggledOutliner\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\t$editorName = $panelName;\n        outlinerEditor -e \n            -showShapes 0\n            -showAssignedMaterials 0\n            -showTimeEditor 1\n            -showReferenceNodes 1\n            -showReferenceMembers 1\n            -showAttributes 0\n            -showConnected 0\n            -showAnimCurvesOnly 0\n            -showMuteInfo 0\n            -organizeByLayer 1\n            -organizeByClip 1\n            -showAnimLayerWeight 1\n            -autoExpandLayers 1\n            -autoExpand 0\n            -showDagOnly 1\n            -showAssets 1\n            -showContainedOnly 1\n            -showPublishedAsConnected 0\n            -showParentContainers 0\n            -showContainerContents 1\n            -ignoreDagHierarchy 0\n            -expandConnections 0\n            -showUpstreamCurves 1\n            -showUnitlessCurves 1\n            -showCompounds 1\n            -showLeafs 1\n            -showNumericAttrsOnly 0\n            -highlightActive 1\n            -autoSelectNewObjects 0\n            -doNotSelectNewObjects 0\n            -dropIsParent 1\n"
		+ "            -transmitFilters 0\n            -setFilter \"defaultSetFilter\" \n            -showSetMembers 1\n            -allowMultiSelection 1\n            -alwaysToggleSelect 0\n            -directSelect 0\n            -isSet 0\n            -isSetMember 0\n            -displayMode \"DAG\" \n            -expandObjects 0\n            -setsIgnoreFilters 1\n            -containersIgnoreFilters 0\n            -editAttrName 0\n            -showAttrValues 0\n            -highlightSecondary 0\n            -showUVAttrsOnly 0\n            -showTextureNodesOnly 0\n            -attrAlphaOrder \"default\" \n            -animLayerFilterOptions \"allAffecting\" \n            -sortOrder \"none\" \n            -longNames 0\n            -niceNames 1\n            -showNamespace 1\n            -showPinIcons 0\n            -mapMotionTrails 0\n            -ignoreHiddenAttribute 0\n            -ignoreOutlinerColor 0\n            -renderFilterVisible 0\n            -renderFilterIndex 0\n            -selectionOrder \"chronological\" \n            -expandAttribute 0\n            $editorName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"outlinerPanel\" (localizedPanelLabel(\"Outliner\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\toutlinerPanel -edit -l (localizedPanelLabel(\"Outliner\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        outlinerEditor -e \n            -showShapes 0\n            -showAssignedMaterials 0\n            -showTimeEditor 1\n            -showReferenceNodes 0\n            -showReferenceMembers 0\n            -showAttributes 0\n            -showConnected 0\n            -showAnimCurvesOnly 0\n            -showMuteInfo 0\n            -organizeByLayer 1\n            -organizeByClip 1\n            -showAnimLayerWeight 1\n            -autoExpandLayers 1\n            -autoExpand 0\n            -showDagOnly 1\n            -showAssets 1\n            -showContainedOnly 1\n            -showPublishedAsConnected 0\n            -showParentContainers 0\n            -showContainerContents 1\n            -ignoreDagHierarchy 0\n"
		+ "            -expandConnections 0\n            -showUpstreamCurves 1\n            -showUnitlessCurves 1\n            -showCompounds 1\n            -showLeafs 1\n            -showNumericAttrsOnly 0\n            -highlightActive 1\n            -autoSelectNewObjects 0\n            -doNotSelectNewObjects 0\n            -dropIsParent 1\n            -transmitFilters 0\n            -setFilter \"defaultSetFilter\" \n            -showSetMembers 1\n            -allowMultiSelection 1\n            -alwaysToggleSelect 0\n            -directSelect 0\n            -displayMode \"DAG\" \n            -expandObjects 0\n            -setsIgnoreFilters 1\n            -containersIgnoreFilters 0\n            -editAttrName 0\n            -showAttrValues 0\n            -highlightSecondary 0\n            -showUVAttrsOnly 0\n            -showTextureNodesOnly 0\n            -attrAlphaOrder \"default\" \n            -animLayerFilterOptions \"allAffecting\" \n            -sortOrder \"none\" \n            -longNames 0\n            -niceNames 1\n            -showNamespace 1\n            -showPinIcons 0\n"
		+ "            -mapMotionTrails 0\n            -ignoreHiddenAttribute 0\n            -ignoreOutlinerColor 0\n            -renderFilterVisible 0\n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"graphEditor\" (localizedPanelLabel(\"Graph Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Graph Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"OutlineEd\");\n            outlinerEditor -e \n                -showShapes 1\n                -showAssignedMaterials 0\n                -showTimeEditor 1\n                -showReferenceNodes 0\n                -showReferenceMembers 0\n                -showAttributes 1\n                -showConnected 1\n                -showAnimCurvesOnly 1\n                -showMuteInfo 0\n                -organizeByLayer 1\n                -organizeByClip 1\n                -showAnimLayerWeight 1\n                -autoExpandLayers 1\n"
		+ "                -autoExpand 1\n                -showDagOnly 0\n                -showAssets 1\n                -showContainedOnly 0\n                -showPublishedAsConnected 0\n                -showParentContainers 1\n                -showContainerContents 0\n                -ignoreDagHierarchy 0\n                -expandConnections 1\n                -showUpstreamCurves 1\n                -showUnitlessCurves 1\n                -showCompounds 0\n                -showLeafs 1\n                -showNumericAttrsOnly 1\n                -highlightActive 0\n                -autoSelectNewObjects 1\n                -doNotSelectNewObjects 0\n                -dropIsParent 1\n                -transmitFilters 1\n                -setFilter \"0\" \n                -showSetMembers 0\n                -allowMultiSelection 1\n                -alwaysToggleSelect 0\n                -directSelect 0\n                -displayMode \"DAG\" \n                -expandObjects 0\n                -setsIgnoreFilters 1\n                -containersIgnoreFilters 0\n                -editAttrName 0\n"
		+ "                -showAttrValues 0\n                -highlightSecondary 0\n                -showUVAttrsOnly 0\n                -showTextureNodesOnly 0\n                -attrAlphaOrder \"default\" \n                -animLayerFilterOptions \"allAffecting\" \n                -sortOrder \"none\" \n                -longNames 0\n                -niceNames 1\n                -showNamespace 1\n                -showPinIcons 1\n                -mapMotionTrails 1\n                -ignoreHiddenAttribute 0\n                -ignoreOutlinerColor 0\n                -renderFilterVisible 0\n                $editorName;\n\n\t\t\t$editorName = ($panelName+\"GraphEd\");\n            animCurveEditor -e \n                -displayKeys 1\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 1\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 1\n                -autoFitTime 0\n                -snapTime \"integer\" \n                -snapValue \"none\" \n                -showResults \"off\" \n"
		+ "                -showBufferCurves \"off\" \n                -smoothness \"fine\" \n                -resultSamples 1\n                -resultScreenSamples 0\n                -resultUpdate \"delayed\" \n                -showUpstreamCurves 1\n                -showCurveNames 0\n                -showActiveCurveNames 0\n                -stackedCurves 0\n                -stackedCurvesMin -1\n                -stackedCurvesMax 1\n                -stackedCurvesSpace 0.2\n                -displayNormalized 0\n                -preSelectionHighlight 0\n                -constrainDrag 0\n                -classicMode 1\n                -valueLinesToggle 1\n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dopeSheetPanel\" (localizedPanelLabel(\"Dope Sheet\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Dope Sheet\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"OutlineEd\");\n"
		+ "            outlinerEditor -e \n                -showShapes 1\n                -showAssignedMaterials 0\n                -showTimeEditor 1\n                -showReferenceNodes 0\n                -showReferenceMembers 0\n                -showAttributes 1\n                -showConnected 1\n                -showAnimCurvesOnly 1\n                -showMuteInfo 0\n                -organizeByLayer 1\n                -organizeByClip 1\n                -showAnimLayerWeight 1\n                -autoExpandLayers 1\n                -autoExpand 0\n                -showDagOnly 0\n                -showAssets 1\n                -showContainedOnly 0\n                -showPublishedAsConnected 0\n                -showParentContainers 1\n                -showContainerContents 0\n                -ignoreDagHierarchy 0\n                -expandConnections 1\n                -showUpstreamCurves 1\n                -showUnitlessCurves 0\n                -showCompounds 1\n                -showLeafs 1\n                -showNumericAttrsOnly 1\n                -highlightActive 0\n"
		+ "                -autoSelectNewObjects 0\n                -doNotSelectNewObjects 1\n                -dropIsParent 1\n                -transmitFilters 0\n                -setFilter \"0\" \n                -showSetMembers 0\n                -allowMultiSelection 1\n                -alwaysToggleSelect 0\n                -directSelect 0\n                -displayMode \"DAG\" \n                -expandObjects 0\n                -setsIgnoreFilters 1\n                -containersIgnoreFilters 0\n                -editAttrName 0\n                -showAttrValues 0\n                -highlightSecondary 0\n                -showUVAttrsOnly 0\n                -showTextureNodesOnly 0\n                -attrAlphaOrder \"default\" \n                -animLayerFilterOptions \"allAffecting\" \n                -sortOrder \"none\" \n                -longNames 0\n                -niceNames 1\n                -showNamespace 1\n                -showPinIcons 0\n                -mapMotionTrails 1\n                -ignoreHiddenAttribute 0\n                -ignoreOutlinerColor 0\n                -renderFilterVisible 0\n"
		+ "                $editorName;\n\n\t\t\t$editorName = ($panelName+\"DopeSheetEd\");\n            dopeSheetEditor -e \n                -displayKeys 1\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 0\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 0\n                -autoFitTime 0\n                -snapTime \"integer\" \n                -snapValue \"none\" \n                -outliner \"dopeSheetPanel1OutlineEd\" \n                -showSummary 1\n                -showScene 0\n                -hierarchyBelow 0\n                -showTicks 1\n                -selectionWindow 0 0 0 0 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"timeEditorPanel\" (localizedPanelLabel(\"Time Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Time Editor\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"clipEditorPanel\" (localizedPanelLabel(\"Trax Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Trax Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = clipEditorNameFromPanel($panelName);\n            clipEditor -e \n                -displayKeys 0\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 0\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 0\n                -autoFitTime 0\n                -snapTime \"none\" \n                -snapValue \"none\" \n                -initialized 0\n                -manageSequencer 0 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"sequenceEditorPanel\" (localizedPanelLabel(\"Camera Sequencer\")) `;\n"
		+ "\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Camera Sequencer\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = sequenceEditorNameFromPanel($panelName);\n            clipEditor -e \n                -displayKeys 0\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 0\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 0\n                -autoFitTime 0\n                -snapTime \"none\" \n                -snapValue \"none\" \n                -initialized 0\n                -manageSequencer 1 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"hyperGraphPanel\" (localizedPanelLabel(\"Hypergraph Hierarchy\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Hypergraph Hierarchy\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\n\t\t\t$editorName = ($panelName+\"HyperGraphEd\");\n            hyperGraph -e \n                -graphLayoutStyle \"hierarchicalLayout\" \n                -orientation \"horiz\" \n                -mergeConnections 0\n                -zoom 1\n                -animateTransition 0\n                -showRelationships 1\n                -showShapes 0\n                -showDeformers 0\n                -showExpressions 0\n                -showConstraints 0\n                -showConnectionFromSelected 0\n                -showConnectionToSelected 0\n                -showConstraintLabels 0\n                -showUnderworld 0\n                -showInvisible 0\n                -transitionFrames 1\n                -opaqueContainers 0\n                -freeform 0\n                -imagePosition 0 0 \n                -imageScale 1\n                -imageEnabled 0\n                -graphType \"DAG\" \n                -heatMapDisplay 0\n                -updateSelection 1\n                -updateNodeAdded 1\n                -useDrawOverrideColor 0\n                -limitGraphTraversal -1\n"
		+ "                -range 0 0 \n                -iconSize \"smallIcons\" \n                -showCachedConnections 0\n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"hyperShadePanel\" (localizedPanelLabel(\"Hypershade\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Hypershade\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"visorPanel\" (localizedPanelLabel(\"Visor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Visor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"nodeEditorPanel\" (localizedPanelLabel(\"Node Editor\")) `;\n\tif ($nodeEditorPanelVisible || $nodeEditorWorkspaceControlOpen) {\n"
		+ "\t\tif (\"\" == $panelName) {\n\t\t\tif ($useSceneConfig) {\n\t\t\t\t$panelName = `scriptedPanel -unParent  -type \"nodeEditorPanel\" -l (localizedPanelLabel(\"Node Editor\")) -mbv $menusOkayInPanels `;\n\n\t\t\t$editorName = ($panelName+\"NodeEditorEd\");\n            nodeEditor -e \n                -allAttributes 0\n                -allNodes 0\n                -autoSizeNodes 1\n                -consistentNameSize 1\n                -createNodeCommand \"nodeEdCreateNodeCommand\" \n                -connectNodeOnCreation 0\n                -connectOnDrop 0\n                -copyConnectionsOnPaste 0\n                -defaultPinnedState 0\n                -additiveGraphingMode 0\n                -settingsChangedCallback \"nodeEdSyncControls\" \n                -traversalDepthLimit -1\n                -keyPressCommand \"nodeEdKeyPressCommand\" \n                -nodeTitleMode \"name\" \n                -gridSnap 0\n                -gridVisibility 1\n                -crosshairOnEdgeDragging 0\n                -popupMenuScript \"nodeEdBuildPanelMenus\" \n                -showNamespace 1\n"
		+ "                -showShapes 1\n                -showSGShapes 0\n                -showTransforms 1\n                -useAssets 1\n                -syncedSelection 1\n                -extendToShapes 1\n                -editorMode \"default\" \n                $editorName;\n\t\t\t}\n\t\t} else {\n\t\t\t$label = `panel -q -label $panelName`;\n\t\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Node Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"NodeEditorEd\");\n            nodeEditor -e \n                -allAttributes 0\n                -allNodes 0\n                -autoSizeNodes 1\n                -consistentNameSize 1\n                -createNodeCommand \"nodeEdCreateNodeCommand\" \n                -connectNodeOnCreation 0\n                -connectOnDrop 0\n                -copyConnectionsOnPaste 0\n                -defaultPinnedState 0\n                -additiveGraphingMode 0\n                -settingsChangedCallback \"nodeEdSyncControls\" \n                -traversalDepthLimit -1\n                -keyPressCommand \"nodeEdKeyPressCommand\" \n"
		+ "                -nodeTitleMode \"name\" \n                -gridSnap 0\n                -gridVisibility 1\n                -crosshairOnEdgeDragging 0\n                -popupMenuScript \"nodeEdBuildPanelMenus\" \n                -showNamespace 1\n                -showShapes 1\n                -showSGShapes 0\n                -showTransforms 1\n                -useAssets 1\n                -syncedSelection 1\n                -extendToShapes 1\n                -editorMode \"default\" \n                $editorName;\n\t\t\tif (!$useSceneConfig) {\n\t\t\t\tpanel -e -l $label $panelName;\n\t\t\t}\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"createNodePanel\" (localizedPanelLabel(\"Create Node\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Create Node\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"polyTexturePlacementPanel\" (localizedPanelLabel(\"UV Editor\")) `;\n"
		+ "\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"UV Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"renderWindowPanel\" (localizedPanelLabel(\"Render View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Render View\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"shapePanel\" (localizedPanelLabel(\"Shape Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tshapePanel -edit -l (localizedPanelLabel(\"Shape Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"posePanel\" (localizedPanelLabel(\"Pose Editor\")) `;\n\tif (\"\" != $panelName) {\n"
		+ "\t\t$label = `panel -q -label $panelName`;\n\t\tposePanel -edit -l (localizedPanelLabel(\"Pose Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dynRelEdPanel\" (localizedPanelLabel(\"Dynamic Relationships\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Dynamic Relationships\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"relationshipPanel\" (localizedPanelLabel(\"Relationship Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Relationship Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"referenceEditorPanel\" (localizedPanelLabel(\"Reference Editor\")) `;\n"
		+ "\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Reference Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"componentEditorPanel\" (localizedPanelLabel(\"Component Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Component Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dynPaintScriptedPanelType\" (localizedPanelLabel(\"Paint Effects\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Paint Effects\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"scriptEditorPanel\" (localizedPanelLabel(\"Script Editor\")) `;\n"
		+ "\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Script Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"profilerPanel\" (localizedPanelLabel(\"Profiler Tool\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Profiler Tool\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"contentBrowserPanel\" (localizedPanelLabel(\"Content Browser\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Content Browser\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"Stereo\" (localizedPanelLabel(\"Stereo\")) `;\n"
		+ "\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Stereo\")) -mbv $menusOkayInPanels  $panelName;\nstring $editorName = ($panelName+\"Editor\");\n            stereoCameraView -e \n                -camera \"persp\" \n                -useInteractiveMode 0\n                -displayLights \"default\" \n                -displayAppearance \"wireframe\" \n                -activeOnly 0\n                -ignorePanZoom 0\n                -wireframeOnShaded 0\n                -headsUpDisplay 1\n                -holdOuts 1\n                -selectionHiliteDisplay 1\n                -useDefaultMaterial 0\n                -bufferMode \"double\" \n                -twoSidedLighting 1\n                -backfaceCulling 0\n                -xray 0\n                -jointXray 0\n                -activeComponentsXray 0\n                -displayTextures 0\n                -smoothWireframe 0\n                -lineWidth 1\n                -textureAnisotropic 0\n                -textureHilight 1\n                -textureSampling 2\n"
		+ "                -textureDisplay \"modulate\" \n                -textureMaxSize 32768\n                -fogging 0\n                -fogSource \"fragment\" \n                -fogMode \"linear\" \n                -fogStart 0\n                -fogEnd 100\n                -fogDensity 0.1\n                -fogColor 0.5 0.5 0.5 1 \n                -depthOfFieldPreview 1\n                -maxConstantTransparency 1\n                -objectFilterShowInHUD 1\n                -isFiltered 0\n                -colorResolution 4 4 \n                -bumpResolution 4 4 \n                -textureCompression 0\n                -transparencyAlgorithm \"frontAndBackCull\" \n                -transpInShadows 0\n                -cullingOverride \"none\" \n                -lowQualityLighting 0\n                -maximumNumHardwareLights 0\n                -occlusionCulling 0\n                -shadingModel 0\n                -useBaseRenderer 0\n                -useReducedRenderer 0\n                -smallObjectCulling 0\n                -smallObjectThreshold -1 \n                -interactiveDisableShadows 0\n"
		+ "                -interactiveBackFaceCull 0\n                -sortTransparent 1\n                -controllers 1\n                -nurbsCurves 1\n                -nurbsSurfaces 1\n                -polymeshes 1\n                -subdivSurfaces 1\n                -planes 1\n                -lights 1\n                -cameras 1\n                -controlVertices 1\n                -hulls 1\n                -grid 1\n                -imagePlane 1\n                -joints 1\n                -ikHandles 1\n                -deformers 1\n                -dynamics 1\n                -particleInstancers 1\n                -fluids 1\n                -hairSystems 1\n                -follicles 1\n                -nCloths 1\n                -nParticles 1\n                -nRigids 1\n                -dynamicConstraints 1\n                -locators 1\n                -manipulators 1\n                -pluginShapes 1\n                -dimensions 1\n                -handles 1\n                -pivots 1\n                -textures 1\n                -strokes 1\n                -motionTrails 1\n"
		+ "                -clipGhosts 1\n                -greasePencils 1\n                -shadows 0\n                -captureSequenceNumber -1\n                -width 0\n                -height 0\n                -sceneRenderFilter 0\n                -displayMode \"centerEye\" \n                -viewColor 0 0 0 1 \n                -useCustomBackground 1\n                $editorName;\n            stereoCameraView -e -viewSelected 0 $editorName;\n            stereoCameraView -e \n                -pluginObjects \"gpuCacheDisplayFilter\" 1 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\tif ($useSceneConfig) {\n        string $configName = `getPanel -cwl (localizedPanelLabel(\"Current Layout\"))`;\n        if (\"\" != $configName) {\n\t\t\tpanelConfiguration -edit -label (localizedPanelLabel(\"Current Layout\")) \n\t\t\t\t-userCreated false\n\t\t\t\t-defaultImage \"vacantCell.xP:/\"\n\t\t\t\t-image \"\"\n\t\t\t\t-sc false\n\t\t\t\t-configString \"global string $gMainPane; paneLayout -e -cn \\\"single\\\" -ps 1 100 100 $gMainPane;\"\n\t\t\t\t-removeAllPanels\n"
		+ "\t\t\t\t-ap false\n\t\t\t\t\t(localizedPanelLabel(\"Persp View\")) \n\t\t\t\t\t\"modelPanel\"\n"
		+ "\t\t\t\t\t\"$panelName = `modelPanel -unParent -l (localizedPanelLabel(\\\"Persp View\\\")) -mbv $menusOkayInPanels `;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera persp` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 32768\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 1\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 642\\n    -height 1301\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t\t\"modelPanel -edit -l (localizedPanelLabel(\\\"Persp View\\\")) -mbv $menusOkayInPanels  $panelName;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera persp` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 32768\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 1\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 642\\n    -height 1301\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t$configName;\n\n            setNamedPanelLayout (localizedPanelLabel(\"Current Layout\"));\n        }\n\n        panelHistory -e -clear mainPanelHistory;\n        sceneUIReplacement -clear;\n\t}\n\n\ngrid -spacing 5 -size 12 -divisions 5 -displayAxes yes -displayGridLines yes -displayDivisionLines yes -displayPerspectiveLabels no -displayOrthographicLabels no -displayAxesBold yes -perspectiveLabelPosition axis -orthographicLabelPosition edge;\nviewManip -drawCompass 0 -compassAngle 0 -frontParameters \"\" -homeParameters \"\" -selectionLockParameters \"\";\n}\n");
	setAttr ".scriptType" 3;
select -noExpand :time1;
	setAttr -alteredValue -keyable on ".caching";
	setAttr -alteredValue -channelBox on ".isHistoricallyInteresting";
	setAttr -alteredValue -keyable on ".nodeState";
	setAttr -channelBox on ".binMembership";
	setAttr -keyable on ".outTime" 21;
	setAttr -alteredValue ".unwarpedTime" 21;
	setAttr -keyable on ".enableTimewarp";
	setAttr -keyable on ".timecodeProductionStart";
	setAttr -alteredValue -keyable on ".timecodeMayaStart";
select -noExpand :hardwareRenderingGlobals;
	setAttr ".enableTextureMaxRes" no;
	setAttr ".textureMaxResolution" 4096;
select -noExpand :renderPartition;
	setAttr -keyable on ".caching";
	setAttr -channelBox on ".isHistoricallyInteresting";
	setAttr -keyable on ".nodeState";
	setAttr -channelBox on ".binMembership";
	setAttr -size 3 ".sets";
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
connectAttr "typeMesh1_translateX.output" "typeMesh1.translateX";
connectAttr "typeMesh1_translateY.output" "typeMesh1.translateY";
connectAttr "typeMesh1_translateZ.output" "typeMesh1.translateZ";
connectAttr "shellDeformer1.outputGeometry[0]" "typeMeshShape1.inMesh";
connectAttr "vectorAdjust1GroupId.groupId" "typeMeshShape1.instObjGroups.objectGroups[0].objectGroupId"
		;
connectAttr "vectorAdjust1Set.memberWireframeColor" "typeMeshShape1.instObjGroups.objectGroups[0].objectGrpColor"
		;
connectAttr "groupId2.groupId" "typeMeshShape1.instObjGroups.objectGroups[1].objectGroupId"
		;
connectAttr "tweakSet1.memberWireframeColor" "typeMeshShape1.instObjGroups.objectGroups[1].objectGrpColor"
		;
connectAttr "shellDeformer1GroupId.groupId" "typeMeshShape1.instObjGroups.objectGroups[2].objectGroupId"
		;
connectAttr "shellDeformer1Set.memberWireframeColor" "typeMeshShape1.instObjGroups.objectGroups[2].objectGrpColor"
		;
connectAttr "groupId10.groupId" "typeMeshShape1.instObjGroups.objectGroups[3].objectGroupId"
		;
connectAttr "tweakSet2.memberWireframeColor" "typeMeshShape1.instObjGroups.objectGroups[3].objectGrpColor"
		;
connectAttr "tweak2.vlist[0].vertex[0]" "typeMeshShape1.tweakLocation";
connectAttr "polyAutoProj1.output" "typeMeshShape1Orig.inMesh";
relationship "link" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "link" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
relationship "link" ":lightLinker1" "typeBlinnSG.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" "typeBlinnSG.message" ":defaultLightSet.message";
connectAttr "layerManager.displayLayerId[0]" "defaultLayer.identification";
connectAttr "renderLayerManager.renderLayerId[0]" "defaultRenderLayer.identification"
		;
connectAttr "typeMesh1.message" "type1.transformMessage";
connectAttr "textMeshGeneratorNode.output" "type1.textInput";
connectAttr "type1.vertsPerChar" "typeExtrude1.vertsPerChar";
connectAttr "groupid1.groupId" "typeExtrude1.capGroupId";
connectAttr "groupid2.groupId" "typeExtrude1.bevelGroupId";
connectAttr "groupid3.groupId" "typeExtrude1.extrudeGroupId";
connectAttr "groupId3.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId4.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId5.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId6.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId7.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId8.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId11.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId12.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId13.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId14.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId15.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId16.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId17.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId18.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId19.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId20.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId21.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId22.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId23.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId24.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId25.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId26.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId27.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId28.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId29.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId30.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId31.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId32.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId33.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId34.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId35.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId36.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId37.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId38.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId39.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId40.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId41.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId42.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId43.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId44.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId45.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId46.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId47.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId48.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId49.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId50.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId51.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId52.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId53.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId54.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId55.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId56.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId57.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId58.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId59.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId60.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId61.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId62.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId63.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId64.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId65.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId66.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId67.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId68.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId69.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId70.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId71.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId72.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId73.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId74.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId75.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId76.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId77.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId78.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId79.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId80.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId81.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId82.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId83.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId84.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId85.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId86.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId87.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId88.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId89.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId90.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId91.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId92.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId93.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId94.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId95.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId96.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId97.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId98.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId99.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId100.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId101.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId102.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId103.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId104.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId105.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId106.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId107.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId108.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId109.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId110.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId111.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId112.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId113.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId114.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId115.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId116.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId117.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId118.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId119.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId120.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId121.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId122.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId123.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId124.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId125.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId126.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId127.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId128.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId129.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId130.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId131.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId132.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId133.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId134.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId135.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId136.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId137.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId138.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId139.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId140.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId141.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId142.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId143.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "groupId144.groupId" "typeExtrude1.charGroupId" -nextAvailable;
connectAttr "type1.outputMesh" "typeExtrude1.inputMesh";
connectAttr "type1.extrudeMessage" "typeExtrude1.typeMessage";
connectAttr "typeBlinn.outColor" "typeBlinnSG.surfaceShader";
connectAttr "typeMeshShape1.instObjGroups" "typeBlinnSG.dagSetMembers" -nextAvailable
		;
connectAttr "typeBlinnSG.message" "materialInfo1.shadingGroup";
connectAttr "typeBlinn.message" "materialInfo1.material";
connectAttr "vectorAdjust1GroupParts.outputGeometry" "vectorAdjust1.input[0].inputGeometry"
		;
connectAttr "vectorAdjust1GroupId.groupId" "vectorAdjust1.input[0].groupId";
connectAttr "type1.grouping" "vectorAdjust1.grouping";
connectAttr "type1.manipulatorTransforms" "vectorAdjust1.manipulatorTransforms";
connectAttr "type1.alignmentMode" "vectorAdjust1.alignmentMode";
connectAttr "type1.vertsPerChar" "vectorAdjust1.vertsPerChar";
connectAttr "typeExtrude1.vertexGroupIds" "vectorAdjust1.vertexGroupIds";
connectAttr "groupParts2.outputGeometry" "tweak1.input[0].inputGeometry";
connectAttr "groupId2.groupId" "tweak1.input[0].groupId";
connectAttr "vectorAdjust1GroupId.message" "vectorAdjust1Set.groupNodes" -nextAvailable
		;
connectAttr "typeMeshShape1.instObjGroups.objectGroups[0]" "vectorAdjust1Set.dagSetMembers"
		 -nextAvailable;
connectAttr "vectorAdjust1.message" "vectorAdjust1Set.usedBy[0]";
connectAttr "tweak1.outputGeometry[0]" "vectorAdjust1GroupParts.inputGeometry";
connectAttr "vectorAdjust1GroupId.groupId" "vectorAdjust1GroupParts.groupId";
connectAttr "groupId2.message" "tweakSet1.groupNodes" -nextAvailable;
connectAttr "typeMeshShape1.instObjGroups.objectGroups[1]" "tweakSet1.dagSetMembers"
		 -nextAvailable;
connectAttr "tweak1.message" "tweakSet1.usedBy[0]";
connectAttr "typeExtrude1.outputMesh" "groupParts2.inputGeometry";
connectAttr "groupId2.groupId" "groupParts2.groupId";
connectAttr "vectorAdjust1.outputGeometry[0]" "polyRemesh1.inputPolymesh";
connectAttr "typeMeshShape1.worldMatrix" "polyRemesh1.manipMatrix";
connectAttr "type1.remeshMessage" "polyRemesh1.typeMessage";
connectAttr "typeExtrude1.capComponents" "polyRemesh1.inputComponents";
connectAttr "polyRemesh1.output" "polyAutoProj1.inputPolymesh";
connectAttr "typeMeshShape1.worldMatrix" "polyAutoProj1.manipMatrix";
connectAttr "shellDeformer1GroupParts.outputGeometry" "shellDeformer1.input[0].inputGeometry"
		;
connectAttr "shellDeformer1GroupId.groupId" "shellDeformer1.input[0].groupId";
connectAttr "type1.animationPosition" "shellDeformer1.animationPosition";
connectAttr "type1.animationPositionX" "shellDeformer1.animationPositionX";
connectAttr "type1.animationPositionY" "shellDeformer1.animationPositionY";
connectAttr "type1.animationPositionZ" "shellDeformer1.animationPositionZ";
connectAttr "type1.animationRotation" "shellDeformer1.animationRotation";
connectAttr "type1.animationRotationX" "shellDeformer1.animationRotationX";
connectAttr "type1.animationRotationY" "shellDeformer1.animationRotationY";
connectAttr "type1.animationRotationZ" "shellDeformer1.animationRotationZ";
connectAttr "type1.animationScale" "shellDeformer1.animationScale";
connectAttr "type1.animationScaleX" "shellDeformer1.animationScaleX";
connectAttr "type1.animationScaleY" "shellDeformer1.animationScaleY";
connectAttr "type1.animationScaleZ" "shellDeformer1.animationScaleZ";
connectAttr "type1.vertsPerChar" "shellDeformer1.vertsPerChar";
connectAttr ":time1.outTime" "shellDeformer1.time";
connectAttr "type1.grouping" "shellDeformer1.grouping";
connectAttr "type1.animationMessage" "shellDeformer1.typeMessage";
connectAttr "typeExtrude1.vertexGroupIds" "shellDeformer1.vertexGroupIds";
connectAttr "groupParts4.outputGeometry" "tweak2.input[0].inputGeometry";
connectAttr "groupId10.groupId" "tweak2.input[0].groupId";
connectAttr "shellDeformer1GroupId.message" "shellDeformer1Set.groupNodes" -nextAvailable
		;
connectAttr "typeMeshShape1.instObjGroups.objectGroups[2]" "shellDeformer1Set.dagSetMembers"
		 -nextAvailable;
connectAttr "shellDeformer1.message" "shellDeformer1Set.usedBy[0]";
connectAttr "tweak2.outputGeometry[0]" "shellDeformer1GroupParts.inputGeometry";
connectAttr "shellDeformer1GroupId.groupId" "shellDeformer1GroupParts.groupId";
connectAttr "groupId10.message" "tweakSet2.groupNodes" -nextAvailable;
connectAttr "typeMeshShape1.instObjGroups.objectGroups[3]" "tweakSet2.dagSetMembers"
		 -nextAvailable;
connectAttr "tweak2.message" "tweakSet2.usedBy[0]";
connectAttr "typeMeshShape1Orig.worldMesh" "groupParts4.inputGeometry";
connectAttr "groupId10.groupId" "groupParts4.groupId";
connectAttr "type1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[0].dependNode"
		;
connectAttr "shellDeformer1Set.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[1].dependNode"
		;
connectAttr "tweak1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[2].dependNode"
		;
connectAttr "tweak2.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[3].dependNode"
		;
connectAttr "tweakSet1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[4].dependNode"
		;
connectAttr "typeBlinnSG.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[6].dependNode"
		;
connectAttr ":time1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[7].dependNode"
		;
connectAttr "vectorAdjust1Set.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[8].dependNode"
		;
connectAttr "vectorAdjust1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[9].dependNode"
		;
connectAttr "shellDeformer1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[10].dependNode"
		;
connectAttr "typeMesh1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[11].dependNode"
		;
connectAttr "tweakSet2.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[12].dependNode"
		;
connectAttr "polyAutoProj1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[13].dependNode"
		;
connectAttr "polyRemesh1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[14].dependNode"
		;
connectAttr "typeExtrude1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[15].dependNode"
		;
connectAttr "typeMeshShape1.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[16].dependNode"
		;
connectAttr "typeMeshShape1Orig.message" "MayaNodeEditorSavedTabsInfo.tabGraphInfo[0].nodeInfo[17].dependNode"
		;
connectAttr "typeMesh1.translate" "textMeshGeneratorNode.inPosition";
connectAttr "typeBlinnSG.partition" ":renderPartition.sets" -nextAvailable;
connectAttr "typeBlinn.message" ":defaultShaderList1.shaders" -nextAvailable;
connectAttr "defaultRenderLayer.message" ":defaultRenderingList1.rendering" -nextAvailable
		;
// End of textMeshGeneratorNode.ma
