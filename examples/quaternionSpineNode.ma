//Maya ASCII 2018ff07 scene
//Name: quaternionSpineNode.ma
//Last modified: Wed, Jan 23, 2019 11:06:50 AM
//Codeset: UTF-8
requires maya "2018ff07";
requires -nodeType "mPyNode" "mpynode_plugin.py" "1.0";
requires "stereoCamera" "10.0";
currentUnit -l centimeter -a degree -t ntsc;
fileInfo "application" "maya";
fileInfo "product" "Maya 2018";
fileInfo "version" "2018";
fileInfo "cutIdentifier" "201711281015-8e846c9074";
fileInfo "osv" "Mac OS X 10.14.2";
createNode transform -s -n "persp";
	rename -uid "8E259036-4AA5-9969-1B8F-78B43E775DA2";
	setAttr ".v" no;
	setAttr ".t" -type "double3" -12.531697332519993 11.835023890474226 5.7725872774655196 ;
	setAttr ".r" -type "double3" -24.338352729603344 300.60000000000349 3.1240627806037878e-15 ;
createNode camera -s -n "perspShape" -p "persp";
	rename -uid "EAD1C557-4831-D914-7EA5-4DBCB06346DC";
	setAttr -k off ".v" no;
	setAttr ".fl" 34.999999999999993;
	setAttr ".coi" 15.5464670288919;
	setAttr ".imn" -type "string" "persp";
	setAttr ".den" -type "string" "persp_depth";
	setAttr ".man" -type "string" "persp_mask";
	setAttr ".hc" -type "string" "viewSet -p %camera";
createNode transform -s -n "top";
	rename -uid "E66E4897-43E5-DAB5-5D2D-0983E62D0817";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 0 1000.1 0 ;
	setAttr ".r" -type "double3" -89.999999999999986 0 0 ;
createNode camera -s -n "topShape" -p "top";
	rename -uid "09DB9656-420D-A46E-5B81-AEB87B11665C";
	setAttr -k off ".v" no;
	setAttr ".rnd" no;
	setAttr ".coi" 1000.1;
	setAttr ".ow" 9.8838896952104491;
	setAttr ".imn" -type "string" "top";
	setAttr ".den" -type "string" "top_depth";
	setAttr ".man" -type "string" "top_mask";
	setAttr ".hc" -type "string" "viewSet -t %camera";
	setAttr ".o" yes;
createNode transform -s -n "front";
	rename -uid "BB342D48-4A86-B191-37D4-51A368FE807D";
	setAttr ".v" no;
	setAttr ".t" -type "double3" -3.5784396813453383 6.1805464607797216 1000.1 ;
createNode camera -s -n "frontShape" -p "front";
	rename -uid "5FA245E2-4905-3DB5-8FC5-D3A260944FA0";
	setAttr -k off ".v" no;
	setAttr ".rnd" no;
	setAttr ".coi" 1000.1;
	setAttr ".ow" 38.892313283673175;
	setAttr ".imn" -type "string" "front";
	setAttr ".den" -type "string" "front_depth";
	setAttr ".man" -type "string" "front_mask";
	setAttr ".hc" -type "string" "viewSet -f %camera";
	setAttr ".o" yes;
createNode transform -s -n "side";
	rename -uid "9490F27B-4762-7309-171C-3582645A7660";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 1000.1 2.1021897810218961 -1.1824817518248154 ;
	setAttr ".r" -type "double3" 0 89.999999999999986 0 ;
createNode camera -s -n "sideShape" -p "side";
	rename -uid "164F4EAE-4132-B7E2-D70C-30B63299AF82";
	setAttr -k off ".v" no;
	setAttr ".rnd" no;
	setAttr ".coi" 1000.1;
	setAttr ".ow" 30;
	setAttr ".imn" -type "string" "side";
	setAttr ".den" -type "string" "side_depth";
	setAttr ".man" -type "string" "side_mask";
	setAttr ".hc" -type "string" "viewSet -s %camera";
	setAttr ".o" yes;
createNode transform -n "curve1";
	rename -uid "FA124C29-419B-A7D3-3C21-90830C32E8B6";
createNode nurbsCurve -n "curveShape1" -p "curve1";
	rename -uid "57E59043-4330-ADAC-0706-60AF2D90F404";
	setAttr -k off ".v";
	setAttr -s 12 ".iog[0].og";
	setAttr ".tw" yes;
createNode nurbsCurve -n "curveShape1Orig" -p "curve1";
	rename -uid "C19DFF21-44F8-390F-50A2-B18EE8A5D733";
	setAttr -k off ".v";
	setAttr ".io" yes;
	setAttr ".cc" -type "nurbsCurve" 
		3 2 0 no 3
		7 0 0 0 1 2 2 2
		5
		0 0 0
		0 3 0
		0 6 0
		0 9 0
		0 12 0
		;
createNode transform -n "group1";
	rename -uid "A1625C26-4A4E-51AF-7ECB-FBA77D9E87F9";
createNode transform -n "locator1" -p "group1";
	rename -uid "A7FD6558-4219-809E-69B1-4EAF96FB769F";
createNode locator -n "locatorShape1" -p "locator1";
	rename -uid "D8619E8C-46AE-053A-2B96-3290B4A4EF56";
	setAttr -k off ".v";
	setAttr ".los" -type "double3" 2 2 2 ;
createNode transform -n "cluster1Handle" -p "locator1";
	rename -uid "07310B2D-461B-04A8-0432-7B8460CD668D";
	setAttr ".v" no;
createNode clusterHandle -n "cluster1HandleShape" -p "cluster1Handle";
	rename -uid "ADD49ECC-42C3-C94B-0232-A88795F89A6B";
	setAttr ".ihi" 0;
	setAttr -k off ".v";
createNode transform -n "locator2" -p "group1";
	rename -uid "081772C1-4CB0-B893-06B2-25AAB8D51FBB";
createNode locator -n "locatorShape2" -p "locator2";
	rename -uid "F04B59AC-4F84-2DAA-0C71-3D91DB6DAAC9";
	setAttr -k off ".v";
	setAttr ".los" -type "double3" 2 2 2 ;
createNode transform -n "cluster2Handle" -p "locator2";
	rename -uid "6124FB0F-4A07-0C3A-FB9F-EA99485DBEF1";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 0 -3 0 ;
	setAttr ".rp" -type "double3" 0 3 0 ;
	setAttr ".sp" -type "double3" 0 3 0 ;
createNode clusterHandle -n "cluster2HandleShape" -p "cluster2Handle";
	rename -uid "02E0AAED-4215-D70E-EF53-2F838B0742A9";
	setAttr ".ihi" 0;
	setAttr -k off ".v";
	setAttr ".or" -type "double3" 0 3 0 ;
createNode transform -n "locator3" -p "group1";
	rename -uid "BACD9C42-4193-ADF2-EC92-F48FF7338A1A";
createNode locator -n "locatorShape3" -p "locator3";
	rename -uid "77566323-44E9-E04D-E0FE-F4919BBFF0C3";
	setAttr -k off ".v";
	setAttr ".los" -type "double3" 2 2 2 ;
createNode transform -n "cluster3Handle" -p "locator3";
	rename -uid "560B1AE9-497C-EA3B-68EE-5D811C502B58";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 0 -6 0 ;
	setAttr ".rp" -type "double3" 0 6 0 ;
	setAttr ".sp" -type "double3" 0 6 0 ;
createNode clusterHandle -n "cluster3HandleShape" -p "cluster3Handle";
	rename -uid "07B581BF-44C3-2AB1-4E7D-9C9DEA3887EE";
	setAttr ".ihi" 0;
	setAttr -k off ".v";
	setAttr ".or" -type "double3" 0 6 0 ;
createNode transform -n "locator4" -p "group1";
	rename -uid "01BB336D-4ED1-FC12-767B-EDA46C8F4916";
createNode locator -n "locatorShape4" -p "locator4";
	rename -uid "72F58B8E-4DF3-4C75-908A-C5B7CC722ACB";
	setAttr -k off ".v";
	setAttr ".los" -type "double3" 2 2 2 ;
createNode transform -n "cluster4Handle" -p "locator4";
	rename -uid "8A3E37F8-4EE7-1A9D-C098-6EA16DD54FB3";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 0 -9 0 ;
	setAttr ".rp" -type "double3" 0 9 0 ;
	setAttr ".sp" -type "double3" 0 9 0 ;
createNode clusterHandle -n "cluster4HandleShape" -p "cluster4Handle";
	rename -uid "67B52132-41AB-5CFA-1D9F-9EBABF91E72A";
	setAttr ".ihi" 0;
	setAttr -k off ".v";
	setAttr ".or" -type "double3" 0 9 0 ;
createNode transform -n "locator5" -p "group1";
	rename -uid "6C4C2192-4362-A711-8280-2F93F9BC1C6E";
createNode locator -n "locatorShape5" -p "locator5";
	rename -uid "6B82D837-4454-79F1-B312-C29EE7897E8D";
	setAttr -k off ".v";
	setAttr ".los" -type "double3" 2 2 2 ;
createNode transform -n "cluster5Handle" -p "locator5";
	rename -uid "95755CF5-4ED6-B215-5462-B08C658F721A";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 0 -12 0 ;
	setAttr ".rp" -type "double3" 0 12 0 ;
	setAttr ".sp" -type "double3" 0 12 0 ;
createNode clusterHandle -n "cluster5HandleShape" -p "cluster5Handle";
	rename -uid "7D9AB130-4E1F-8AB1-C7AF-029E73540CBF";
	setAttr ".ihi" 0;
	setAttr -k off ".v";
	setAttr ".or" -type "double3" 0 12 0 ;
createNode transform -n "group2";
	rename -uid "3D77EC16-4C05-F437-F0D8-E3B4E18CEDEC";
createNode transform -n "pCube1" -p "group2";
	rename -uid "3651A5EF-4B28-5E3B-0BAB-D181C4493269";
	addAttr -ci true -sn "u" -ln "u" -at "double";
	setAttr ".dla" yes;
	setAttr -k on ".u";
createNode mesh -n "pCubeShape1" -p "pCube1";
	rename -uid "730F03D5-454E-FD27-1EA7-25834F522634";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr ".tgsp" 1;
createNode transform -n "pCube2" -p "group2";
	rename -uid "C6C3AE27-45F4-7408-142F-1FA90B7DC31F";
	addAttr -ci true -sn "u" -ln "u" -at "double";
	setAttr ".dla" yes;
	setAttr -k on ".u";
createNode mesh -n "pCubeShape2" -p "pCube2";
	rename -uid "97DF9DD6-4DF7-3545-58AA-0CABD1EE29A8";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 14 ".uvst[0].uvsp[0:13]" -type "float2" 0.375 0 0.625 0 0.375
		 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1 0.625 1 0.875 0
		 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr -s 8 ".vt[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 0.5 0.5 0.5
		 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -s 12 ".ed[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0 2 4 0
		 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -s 6 -ch 24 ".fc[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".cvd" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pd[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".hfd" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tgsp" 1;
createNode transform -n "pCube3" -p "group2";
	rename -uid "6BDD74FE-431C-B852-80F9-1A97A81A7989";
	addAttr -ci true -sn "u" -ln "u" -at "double";
	setAttr ".dla" yes;
	setAttr -k on ".u";
createNode mesh -n "pCubeShape3" -p "pCube3";
	rename -uid "1786FAEF-4DF1-75B9-48E4-759E5BBF2A37";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 14 ".uvst[0].uvsp[0:13]" -type "float2" 0.375 0 0.625 0 0.375
		 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1 0.625 1 0.875 0
		 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr -s 8 ".vt[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 0.5 0.5 0.5
		 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -s 12 ".ed[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0 2 4 0
		 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -s 6 -ch 24 ".fc[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".cvd" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pd[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".hfd" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tgsp" 1;
createNode transform -n "pCube4" -p "group2";
	rename -uid "EFACDA95-412D-76AA-8CA1-8789819C3BFE";
	addAttr -ci true -sn "u" -ln "u" -at "double";
	setAttr ".dla" yes;
	setAttr -k on ".u";
createNode mesh -n "pCubeShape4" -p "pCube4";
	rename -uid "1653E180-4940-9D58-94FB-9E8C416906FD";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 14 ".uvst[0].uvsp[0:13]" -type "float2" 0.375 0 0.625 0 0.375
		 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1 0.625 1 0.875 0
		 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr -s 8 ".vt[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 0.5 0.5 0.5
		 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -s 12 ".ed[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0 2 4 0
		 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -s 6 -ch 24 ".fc[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".cvd" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pd[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".hfd" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tgsp" 1;
createNode transform -n "pCube5" -p "group2";
	rename -uid "16DE0823-410A-8C94-8DF4-CCB3FE330C79";
	addAttr -ci true -sn "u" -ln "u" -at "double";
	setAttr ".dla" yes;
	setAttr -k on ".u";
createNode mesh -n "pCubeShape5" -p "pCube5";
	rename -uid "FBE0E17D-4682-E7F9-6277-B68CAE7FAA32";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 14 ".uvst[0].uvsp[0:13]" -type "float2" 0.375 0 0.625 0 0.375
		 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1 0.625 1 0.875 0
		 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr -s 8 ".vt[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 0.5 0.5 0.5
		 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -s 12 ".ed[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0 2 4 0
		 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -s 6 -ch 24 ".fc[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".cvd" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pd[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".hfd" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tgsp" 1;
createNode transform -n "pCube6" -p "group2";
	rename -uid "E7F7D440-41F5-68E2-7FBD-D3B61AEF5703";
	addAttr -ci true -sn "u" -ln "u" -at "double";
	setAttr ".dla" yes;
	setAttr -k on ".u";
createNode mesh -n "pCubeShape6" -p "pCube6";
	rename -uid "300BEF71-4F3D-10DA-36CE-C291593867BE";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 14 ".uvst[0].uvsp[0:13]" -type "float2" 0.375 0 0.625 0 0.375
		 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1 0.625 1 0.875 0
		 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr -s 8 ".vt[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 0.5 0.5 0.5
		 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -s 12 ".ed[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0 2 4 0
		 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -s 6 -ch 24 ".fc[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".cvd" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pd[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".hfd" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tgsp" 1;
createNode transform -n "pCube7" -p "group2";
	rename -uid "510F7811-498C-EACB-1E66-FEADC230E2DC";
	addAttr -ci true -sn "u" -ln "u" -at "double";
	setAttr ".dla" yes;
	setAttr -k on ".u";
createNode mesh -n "pCubeShape7" -p "pCube7";
	rename -uid "80FB80A3-497A-39E7-2E7A-CC92D9143A6E";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 14 ".uvst[0].uvsp[0:13]" -type "float2" 0.375 0 0.625 0 0.375
		 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1 0.625 1 0.875 0
		 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr -s 8 ".vt[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 0.5 0.5 0.5
		 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -s 12 ".ed[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0 2 4 0
		 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -s 6 -ch 24 ".fc[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".cvd" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pd[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".hfd" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tgsp" 1;
createNode transform -n "pCube8" -p "group2";
	rename -uid "65344124-4017-D918-DF3D-D0B093669458";
	addAttr -ci true -sn "u" -ln "u" -at "double";
	setAttr ".dla" yes;
	setAttr -k on ".u";
createNode mesh -n "pCubeShape8" -p "pCube8";
	rename -uid "809B7931-43B2-BC50-62BE-D6BB69CBAB9E";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 14 ".uvst[0].uvsp[0:13]" -type "float2" 0.375 0 0.625 0 0.375
		 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1 0.625 1 0.875 0
		 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr -s 8 ".vt[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 0.5 0.5 0.5
		 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -s 12 ".ed[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0 2 4 0
		 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -s 6 -ch 24 ".fc[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".cvd" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pd[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".hfd" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tgsp" 1;
createNode transform -n "pCube9" -p "group2";
	rename -uid "1D28CA0B-4932-0605-42DB-B190C782D0F1";
	addAttr -ci true -sn "u" -ln "u" -at "double";
	setAttr ".dla" yes;
	setAttr -k on ".u";
createNode mesh -n "pCubeShape9" -p "pCube9";
	rename -uid "2FDEE6F1-4024-7007-2C64-3BB4798E5F96";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 14 ".uvst[0].uvsp[0:13]" -type "float2" 0.375 0 0.625 0 0.375
		 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1 0.625 1 0.875 0
		 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr -s 8 ".vt[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 0.5 0.5 0.5
		 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -s 12 ".ed[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0 2 4 0
		 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -s 6 -ch 24 ".fc[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".cvd" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pd[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".hfd" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tgsp" 1;
createNode transform -n "pCube10" -p "group2";
	rename -uid "0C0A25E1-4905-7E03-A33D-F7B01D3488E8";
	addAttr -ci true -sn "u" -ln "u" -at "double";
	setAttr ".dla" yes;
	setAttr -k on ".u";
createNode mesh -n "pCubeShape10" -p "pCube10";
	rename -uid "65722D0C-4B5D-DAF0-9E46-DC87F336F51C";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 14 ".uvst[0].uvsp[0:13]" -type "float2" 0.375 0 0.625 0 0.375
		 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1 0.625 1 0.875 0
		 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr -s 8 ".vt[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 0.5 0.5 0.5
		 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -s 12 ".ed[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0 2 4 0
		 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -s 6 -ch 24 ".fc[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".cvd" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pd[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".hfd" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tgsp" 1;
createNode transform -n "pCube11" -p "group2";
	rename -uid "2586CE0D-4B20-6C91-7F71-01AADEE95628";
	addAttr -ci true -sn "u" -ln "u" -at "double";
	setAttr ".dla" yes;
	setAttr -k on ".u";
createNode mesh -n "pCubeShape11" -p "pCube11";
	rename -uid "F0EDA641-417F-F26F-21FE-C58B46A74273";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 14 ".uvst[0].uvsp[0:13]" -type "float2" 0.375 0 0.625 0 0.375
		 0.25 0.625 0.25 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1 0.625 1 0.875 0
		 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr -s 8 ".vt[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 0.5 0.5 0.5
		 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -s 12 ".ed[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0 2 4 0
		 3 5 0 4 6 0 5 7 0 6 0 0 7 1 0;
	setAttr -s 6 -ch 24 ".fc[0:5]" -type "polyFaces" 
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".cvd" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pd[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".hfd" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".tgsp" 1;
createNode lightLinker -s -n "lightLinker1";
	rename -uid "44946C1C-B94B-937E-89A1-BAABF67F011E";
	setAttr -s 2 ".lnk";
	setAttr -s 2 ".slnk";
createNode shapeEditorManager -n "shapeEditorManager";
	rename -uid "56E1F8FB-724F-CF71-0A87-89B259CB51FA";
createNode poseInterpolatorManager -n "poseInterpolatorManager";
	rename -uid "76051B73-D445-E56F-6B3D-759A1DF4EE0F";
createNode displayLayerManager -n "layerManager";
	rename -uid "E557C06E-7B40-2C17-BBC3-1581154174E0";
createNode displayLayer -n "defaultLayer";
	rename -uid "CBDE64CC-4234-AB21-6BE9-4291DC6883B9";
createNode renderLayerManager -n "renderLayerManager";
	rename -uid "1894A6CC-6749-39A5-61CE-98B0F79747EE";
createNode renderLayer -n "defaultRenderLayer";
	rename -uid "2437A304-4D80-C9B3-240D-A09911FB62E7";
	setAttr ".g" yes;
createNode cluster -n "cluster1";
	rename -uid "F1EE99B4-44CB-77F7-8C0D-EC9F01571186";
	setAttr ".gm[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".ait" 0;
createNode tweak -n "tweak1";
	rename -uid "A1B93EC3-4C00-716B-A3D0-95A50E44E8DD";
createNode objectSet -n "cluster1Set";
	rename -uid "FBBBC84F-440C-1E6A-0171-3EA03872BFDA";
	setAttr ".ihi" 0;
	setAttr ".vo" yes;
createNode groupId -n "cluster1GroupId";
	rename -uid "C227A703-4486-EF6B-9AC8-1FA0FB50DAFC";
	setAttr ".ihi" 0;
createNode groupParts -n "cluster1GroupParts";
	rename -uid "7D4AC451-4EBF-DF4B-0340-3A8BACC7139B";
	setAttr ".ihi" 0;
	setAttr ".ic" -type "componentList" 1 "cv[0]";
createNode objectSet -n "tweakSet1";
	rename -uid "114265B4-4403-4F1F-81D4-BEAB03FB5C57";
	setAttr ".ihi" 0;
	setAttr ".vo" yes;
createNode groupId -n "groupId2";
	rename -uid "51C4197E-41CC-9BC8-C58B-65BA2A732C69";
	setAttr ".ihi" 0;
createNode groupParts -n "groupParts2";
	rename -uid "0DDFD21E-4F4A-A7A6-5E90-14B8765A9C9A";
	setAttr ".ihi" 0;
	setAttr ".ic" -type "componentList" 1 "cv[*]";
createNode cluster -n "cluster2";
	rename -uid "36261759-4E86-6F2D-F80A-DE8DFA96BE0F";
	setAttr ".gm[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".ait" 0;
createNode objectSet -n "cluster2Set";
	rename -uid "713971F3-4DA1-6B07-06B5-8B8E9F803500";
	setAttr ".ihi" 0;
	setAttr ".vo" yes;
createNode groupId -n "cluster2GroupId";
	rename -uid "235C4134-4953-5DFE-FE75-02A4E4BF26B3";
	setAttr ".ihi" 0;
createNode groupParts -n "cluster2GroupParts";
	rename -uid "9E096AF5-41F1-5A70-9E92-D992439B424A";
	setAttr ".ihi" 0;
	setAttr ".ic" -type "componentList" 1 "cv[1]";
createNode cluster -n "cluster3";
	rename -uid "87F356CE-413B-7858-FBF4-ED9AEAFF456D";
	setAttr ".gm[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".ait" 0;
createNode objectSet -n "cluster3Set";
	rename -uid "4161B9D5-4D90-0087-EF06-6FB7BE845F4A";
	setAttr ".ihi" 0;
	setAttr ".vo" yes;
createNode groupId -n "cluster3GroupId";
	rename -uid "7FBF5E68-43FF-5651-EBAE-B08134B96CA5";
	setAttr ".ihi" 0;
createNode groupParts -n "cluster3GroupParts";
	rename -uid "2AA13D06-49C8-8469-83F0-CD9F8FFA8D1C";
	setAttr ".ihi" 0;
	setAttr ".ic" -type "componentList" 1 "cv[2]";
createNode cluster -n "cluster4";
	rename -uid "279F5287-4ABA-EC2A-D4F9-98A471BF3F6B";
	setAttr ".gm[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".ait" 0;
createNode objectSet -n "cluster4Set";
	rename -uid "42E09FAA-4B05-997F-56E4-A69CE37C76B4";
	setAttr ".ihi" 0;
	setAttr ".vo" yes;
createNode groupId -n "cluster4GroupId";
	rename -uid "C805E092-463C-F784-F091-B096A22372C8";
	setAttr ".ihi" 0;
createNode groupParts -n "cluster4GroupParts";
	rename -uid "73D99EC5-4BA6-1401-0F04-3EB00F5C0B08";
	setAttr ".ihi" 0;
	setAttr ".ic" -type "componentList" 1 "cv[3]";
createNode cluster -n "cluster5";
	rename -uid "2EF5FB32-4A44-D077-96F7-A09EDBAB0191";
	setAttr ".gm[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".ait" 0;
createNode objectSet -n "cluster5Set";
	rename -uid "E4C2E547-4B85-0FD9-82A1-D88BF764F502";
	setAttr ".ihi" 0;
	setAttr ".vo" yes;
createNode groupId -n "cluster5GroupId";
	rename -uid "0AEE83BB-4F7A-C5AB-273A-E194BB15CB22";
	setAttr ".ihi" 0;
createNode groupParts -n "cluster5GroupParts";
	rename -uid "A8E5C018-4474-448C-FD32-DF8FF7F82F98";
	setAttr ".ihi" 0;
	setAttr ".ic" -type "componentList" 1 "cv[4]";
createNode mPyNode -n "spineNode";
	rename -uid "280D4CCF-4053-5D2C-D0DD-E1A5AFE8ACAE";
	addAttr -r false -ci true -k true -sn "inputCurve" -ln "inputCurve" -dt "nurbsCurve";
	addAttr -r false -ci true -k true -m -sn "controlMatrices" -ln "controlMatrices" 
		-at "matrix";
	addAttr -w false -s false -k true -m -sn "outputScale" -ln "outputScale" -at "double3" 
		-nc 3;
	addAttr -w false -s false -k true -sn "outputScaleX" -ln "outputScaleX" -at "double" 
		-p "outputScale";
	addAttr -w false -s false -k true -sn "outputScaleY" -ln "outputScaleY" -at "double" 
		-p "outputScale";
	addAttr -w false -s false -k true -sn "outputScaleZ" -ln "outputScaleZ" -at "double" 
		-p "outputScale";
	addAttr -w false -s false -k true -m -sn "outputRotate" -ln "outputRotate" -at "double3" 
		-nc 3;
	addAttr -w false -s false -k true -sn "outputRotateX" -ln "outputRotateX" -at "doubleAngle" 
		-p "outputRotate";
	addAttr -w false -s false -k true -sn "outputRotateY" -ln "outputRotateY" -at "doubleAngle" 
		-p "outputRotate";
	addAttr -w false -s false -k true -sn "outputRotateZ" -ln "outputRotateZ" -at "doubleAngle" 
		-p "outputRotate";
	addAttr -w false -s false -k true -m -sn "outputTranslate" -ln "outputTranslate" 
		-at "double3" -nc 3;
	addAttr -w false -s false -k true -sn "outputTranslateX" -ln "outputTranslateX" 
		-at "double" -p "outputTranslate";
	addAttr -w false -s false -k true -sn "outputTranslateY" -ln "outputTranslateY" 
		-at "double" -p "outputTranslate";
	addAttr -w false -s false -k true -sn "outputTranslateZ" -ln "outputTranslateZ" 
		-at "double" -p "outputTranslate";
	addAttr -r false -ci true -k true -sn "stretch" -ln "stretch" -at "double";
	addAttr -r false -ci true -k true -sn "pivot" -ln "pivot" -at "double";
	addAttr -r false -ci true -k true -sn "shift" -ln "shift" -at "double";
	addAttr -r false -ci true -k true -sn "scale" -ln "scale" -at "double";
	addAttr -r false -ci true -m -sn "samples" -ln "samples" -at "double";
	addAttr -r false -ci true -k true -sn "resetDefaultLength" -ln "resetDefaultLength" 
		-min 0 -max 1 -en "False:True" -at "enum";
	addAttr -r false -ci true -k true -sn "curveInvertAimAxis" -ln "curveInvertAimAxis" 
		-min 0 -max 1 -en "False:True" -at "enum";
	addAttr -r false -ci true -k true -sn "curveInvertUpAxis" -ln "curveInvertUpAxis" 
		-min 0 -max 1 -en "False:True" -at "enum";
	addAttr -r false -ci true -k true -sn "curveAimAxis" -ln "curveAimAxis" -min 0 -max 
		2 -en "X:Y:Z" -at "enum";
	addAttr -r false -ci true -k true -sn "curveUpAxis" -ln "curveUpAxis" -min 0 -max 
		2 -en "X:Y:Z" -at "enum";
	addAttr -r false -ci true -k true -sn "scaleMethod" -ln "scaleMethod" -min 0 -max 
		2 -en "Square Root:Linear:Cosine" -at "enum";
	setAttr ".ex" -type "string" (
		"# Name: Re-rootable Quaternion Spine\n# Author: Eric Vignola - eric.vignola@gmail.com\n# \n# Demonstrates: - Persistant (flagged as storable) and non persistent attributes\n#               - Node awareness of number of connected outputs\n#               - Usage of a nurbsCurve type attribute to gather information such as the curve's length\n#\n# Explanation: This is an example of a so called \"quaternion spine\". Locators control the spine and transforms\n#              connected to the outputs will be driven by the spine.\n#              \n#              This spine features several things:\n#              - The spine can maintain its default length, or stretch (using the stretch node attribute)\n#              - When not stretched, the node can be rooted at any point (using the pivot node attribute)\n#              - Transforms moved on the spine can have their orientations changed via the aim/up axis node attributes\n#              - Transforms moved on the spine will inherit the transformations of the control points.\n#\n# For fun: - Select the driving locator and drag it around to see the effect.\n"
		+ "#          - Change the pivot attribute to reroot the spine\n#          - Change the scale attribute to scale from pivot position\n#          - Change the shift attribute to shift along the spine\n#          - Change the stretch attribute to keep the spine length when controls are pulled\n#          - Change the scale method to interpolate scale using sqrt (maya's way), linear or cosine\n#          - Select a spine transform (the cubes), and change it's U parameter to affect its position along the spine.\n\n\n\nfrom bisect import bisect_left as bl\nimport math\n\n\ndef vectorToMatrix(V0,V1,aim_axis=0,up_axis=1):\n    \"\"\" Computes an orthogonal 4x4 matrix from an \"aim_vector\" (V0) and an \"up_vector\" (V1).\n        aim/up_axis defined as indices such as 0=X, 1=Y, 2=Z.\n        \n        There might be something built-in that does this, but couldn't find anything\n    \"\"\"\n\n    # Make sure vectors are unit\n    zero = om.MVector()\n    V0 = V0.normal()\n    V1 = V1.normal()\n    V2 = (V1^V0).normalize()\n\n    # Figure out which axis we're trying to extrapolate\n"
		+ "    right_axis = (min([aim_axis,up_axis])-max([aim_axis,up_axis])+min([aim_axis,up_axis]))%3\n    flip = 0\n    if aim_axis == 0 and up_axis == 2:\n        flip = 1\n    elif aim_axis == 1 and up_axis == 0:\n        flip = 1\n    elif aim_axis == 2 and up_axis == 1:\n        flip = 1\n\n    # Compose final matrix from given vectors, there might be a better to do this.\n    aim_axis*=4\n    up_axis*=4\n    right_axis*=4\n    \n    XYZ = om.MMatrix()\n    for i in xrange(3):\n        XYZ[aim_axis+i]   = V0[i]\n        XYZ[up_axis+i]    = V1[i]\n        \n        if flip:\n            XYZ[right_axis+i] = 0 - V2[i]\n        else:\n            XYZ[right_axis+i] = V2[i]\n        \n    return XYZ\n\n\n\n\n#---------------------- Main ----------------------#\n\n\n# Get the current curve length from its highest parameter\nmax_parameter = inputCurve.findParamFromLength(10**9)\ncurrentLength = inputCurve.findLengthFromParam(max_parameter)\n\n\n# Reset default length if required\nif resetDefaultLength:\n    self.defaultLength = currentLength\n\n\n# Calcullate end points and end tangents for projections beyond the curve's limits\n"
		+ "t0 = inputCurve.tangent(0, space=om.MSpace.kWorld)\nt1 = inputCurve.tangent(max_parameter, space=om.MSpace.kWorld)\n\np0 = inputCurve.getPointAtParam(0,space=om.MSpace.kWorld)\np1 = inputCurve.getPointAtParam(max_parameter,space=om.MSpace.kWorld)\n\n\n\n# Calculate normalized control parameters to be used as a control key\nkeys = [0]\nM    = []\nfor i in xrange(len(controlMatrices)):\n    M.append(om.MTransformationMatrix(controlMatrices[i]))\n    \n    if i > 0:\n        dist = om.MPoint(M[i].translation(om.MSpace.kWorld)).distanceTo(om.MPoint(M[i-1].translation(om.MSpace.kWorld))) + keys[i-1]\n        keys.append(dist)\n\nfor i in xrange(1, len(keys)):\n    keys[i] /= keys[-1]\n\n\n\n# Calculate curve length ratio and delta to calculate stretch\nratio = self.defaultLength/currentLength\ndelta = (currentLength - self.defaultLength) / currentLength\n\n\n# Process each spine transform\nfor i in xrange(len(outputTranslate)):\n    \n    \n    # -- POSITION -- #\n    u = shift + pivot + (((((samples[i]*ratio + delta*pivot) * (1 - stretch)) + samples[i]*stretch) - pivot) * scale)\n"
		+ "    w = inputCurve.findParamFromLength(u*currentLength)\n\n    # If query is outside curve borders, use a projection\n    if u < 0:\n        outputTranslate[i] = (p0 + t0 * (u * currentLength))\n\n    elif u > 1:\n        outputTranslate[i] = (p1 + t1 * ((u-1) * currentLength))\n        \n    else:\n        outputTranslate[i] = (inputCurve.getPointAtParam(w,space=om.MSpace.kWorld))\n\n\n\n    # -- ROTATION -- #\n\n    # Find lower bound index\n    index = bl(keys,u)-1\n    if index < 0:\n        index = 0\n    elif index == len(keys)-1:\n        index -= 1\n        \n    \n    # Get the up vectors on each border\n    Q0 = M[index].rotation(asQuaternion=True)\n    Q1 = M[index+1].rotation(asQuaternion=True)\n\n    blend = (u - keys[index]) / (keys[index+1] - keys[index])\n    blend = max(min(blend, 1), 0)\n    slerp = om.MQuaternion.slerp(Q0,Q1,blend).asMatrix()\n\n\n    normal = om.MVector(list(slerp)[curveUpAxis*4:curveUpAxis*4+3])\n    tangent = inputCurve.tangent(w, space=om.MSpace.kWorld)\n\n    if curveInvertUpAxis:\n        normal = om.MVector([0,0,0])-normal\n"
		+ "        \n    if curveInvertAimAxis:\n        tangent = om.MVector([0,0,0])-tangent\n        \n        \n    outputRotate[i] = om.MTransformationMatrix(vectorToMatrix(tangent,normal,curveAimAxis,curveUpAxis)).rotation()\n    \n\n\n    # -- SCALE -- #\n\n    # sqrt\n    if scaleMethod == 0:\n        s0 = om.MVector([abs(x) ** (1-blend) for x in M[index].scale(om.MSpace.kWorld)])\n        s1 = om.MVector([abs(x) **    blend  for x in M[index+1].scale(om.MSpace.kWorld)])\n        outputScale[i] = [a*b for a,b in zip(s0,s1)]\n\n    # linear/cosine\n    else:\n        if scaleMethod == 2:\n            blend = 1-((math.cos(math.radians(blend*180))+1)*0.5)\n        \n        outputScale[i] = (om.MVector(M[index+1].scale(om.MSpace.kWorld)) * blend) + (om.MVector(M[index].scale(om.MSpace.kWorld)) * (1-blend))\n\n\n");
	setAttr "._inputAttrs" -type "string" "gAJ9cQEoWAUAAABzY2FsZV1xAlgFAAAAZmxvYXRxA2FYBwAAAHN0cmV0Y2hdcQRYBQAAAGZsb2F0\ncQVhWAUAAABzaGlmdF1xBlgFAAAAZmxvYXRxB2FYEQAAAGN1cnZlSW52ZXJ0VXBBeGlzXXEIWAQA\nAABlbnVtcQlhWBIAAABjdXJ2ZUludmVydEFpbUF4aXNdcQpYBAAAAGVudW1xC2FYDwAAAGNvbnRy\nb2xNYXRyaWNlc11xDFgGAAAAbWF0cml4cQ1hWAsAAABzY2FsZU1ldGhvZHEOXXEPWAQAAABlbnVt\ncRBhWAcAAABzYW1wbGVzXXERWAUAAABmbG9hdHESYVgFAAAAcGl2b3RdcRNYBQAAAGZsb2F0cRRh\nWAsAAABjdXJ2ZVVwQXhpc11xFVgEAAAAZW51bXEWYVUKaW5wdXRDdXJ2ZV1xF1UKbnVyYnNDdXJ2\nZXEYYVgSAAAAcmVzZXREZWZhdWx0TGVuZ3RoXXEZWAQAAABlbnVtcRphWAwAAABjdXJ2ZUFpbUF4\naXNdcRtYBAAAAGVudW1xHGF1Lg==\n";
	setAttr "._outputAttrs" -type "string" "(dp1\nS'outputScale'\np2\n(lp3\nS'vector'\np4\nasVoutputTranslate\np5\n(lp6\nVvector\np7\nasVoutputRotate\np8\n(lp9\nVeuler\np10\nas.";
	setAttr "._storedVarNames" -type "string" "(lp1\nS'defaultLength'\np2\na.";
	setAttr "._storedVarsData" -type "string" "gAJ9cQFVDWRlZmF1bHRMZW5ndGhxAkdAKAAAAAAAAHMu\n";
	setAttr -k on ".inputCurve";
	setAttr -s 5 ".controlMatrices";
	setAttr -k on ".controlMatrices[0]";
	setAttr -k on ".controlMatrices[1]";
	setAttr -k on ".controlMatrices[2]";
	setAttr -k on ".controlMatrices[3]";
	setAttr -k on ".controlMatrices[4]";
	setAttr -k on ".controlMatrices";
	setAttr -s 11 ".outputScale";
	setAttr -s 11 ".outputRotate";
	setAttr -s 11 ".outputTranslate";
	setAttr -k on ".scale" 1;
	setAttr -s 11 -k on ".samples";
	setAttr -s 11 -k on ".samples";
	setAttr -k on ".curveInvertUpAxis" 1;
	setAttr -k on ".curveAimAxis" 1;
	setAttr -k on ".curveUpAxis" 2;
createNode polyCube -n "polyCube1";
	rename -uid "F5B8A29D-47E9-4DF6-040A-FF9F753EB9D4";
	setAttr ".cuv" 4;
createNode animCurveTL -n "locator3_translateX";
	rename -uid "452E8749-474B-11EF-7FFA-15AA3D7784BD";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0;
createNode animCurveTL -n "locator3_translateY";
	rename -uid "4CF2FCF8-441C-FB47-0EC1-C88900C18C22";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 6;
createNode animCurveTL -n "locator3_translateZ";
	rename -uid "FA919A09-46C2-DE24-EA89-A9AB6EBC0B8E";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0;
createNode animCurveTL -n "locator2_translateX";
	rename -uid "54C71D34-416C-5EEF-53DB-4C8E79DBD115";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0;
createNode animCurveTL -n "locator2_translateY";
	rename -uid "516CAEA6-49B8-F94F-9B4D-16856E0A8A54";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 3;
createNode animCurveTL -n "locator2_translateZ";
	rename -uid "89062B76-4C3F-0A77-50A9-4389474AD8D2";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0;
createNode animCurveTL -n "locator4_translateX";
	rename -uid "E480FC4B-498D-6A9D-49A8-AC9786001D0D";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0;
createNode animCurveTL -n "locator4_translateY";
	rename -uid "F48C9BFC-4290-9CED-7D2D-73BCC7847039";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 9;
createNode animCurveTL -n "locator4_translateZ";
	rename -uid "C1509EED-4E83-B3E1-0C9F-23AC2267D250";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0;
createNode animCurveTL -n "locator1_translateX";
	rename -uid "1DF6804A-417B-260F-8BEC-7A85495FA230";
	setAttr ".tan" 18;
	setAttr -s 3 ".ktv[0:2]"  0 0 30 0 60 0;
createNode animCurveTL -n "locator1_translateY";
	rename -uid "472D6A63-4CBD-BD0F-3B83-C7BC6ABAB4AC";
	setAttr ".tan" 18;
	setAttr -s 3 ".ktv[0:2]"  0 0 30 0 60 0;
createNode animCurveTL -n "locator1_translateZ";
	rename -uid "FF681171-4047-4D54-14D7-EA8E149D28BF";
	setAttr ".tan" 18;
	setAttr -s 3 ".ktv[0:2]"  0 -5 30 5 60 -5;
	setAttr ".pre" 3;
	setAttr ".pst" 3;
createNode script -n "sceneConfigurationScriptNode";
	rename -uid "DE2B8F22-40CF-ACEC-9C0B-D5AD9C941373";
	setAttr ".b" -type "string" "playbackOptions -min 0 -max 200 -ast 0 -aet 200 ";
	setAttr ".st" 6;
createNode animCurveTU -n "pCube11_u";
	rename -uid "51E77AD4-4101-466A-8067-4D88BCBB2D37";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 1;
createNode animCurveTU -n "pCube1_u";
	rename -uid "A7F27170-46B8-82D2-1CAE-B1ACDE84BB52";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0;
createNode animCurveTU -n "pCube2_u";
	rename -uid "2856B004-44CE-F187-9FD8-A7BE05F2C55B";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0.1;
createNode animCurveTU -n "pCube3_u";
	rename -uid "87FA9512-421B-5996-DC7B-0BB0F2E5F8C4";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0.2;
createNode animCurveTU -n "pCube4_u";
	rename -uid "933F97ED-4236-5615-7539-AC8BD9F6E67A";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0.3;
createNode animCurveTU -n "pCube5_u";
	rename -uid "36937CB6-40F7-FD06-FA2C-A994951B3DE2";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0.4;
createNode animCurveTU -n "pCube6_u";
	rename -uid "1707FFB0-49C8-5A87-18FF-179E4653459D";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0.5;
createNode animCurveTU -n "pCube7_u";
	rename -uid "C34C6AA1-465E-7CB9-76D7-5595DEEEA44A";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0.6;
createNode animCurveTU -n "pCube8_u";
	rename -uid "E8374708-4CE8-6087-497F-C2AF43A10C94";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0.7;
createNode animCurveTU -n "pCube9_u";
	rename -uid "921E2089-4ECB-A8FF-1416-1CA2D4DE77E6";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0.8;
createNode animCurveTU -n "pCube10_u";
	rename -uid "12E88FBE-4667-6CE5-CC9F-79A29DAF30E9";
	setAttr ".tan" 18;
	setAttr ".ktv[0]"  0 0.9;
createNode script -n "uiConfigurationScriptNode";
	rename -uid "AD92A617-4FAD-7A75-8478-61BCEADE3D0C";
	setAttr ".b" -type "string" (
		"// Maya Mel UI Configuration File.\n//\n//  This script is machine generated.  Edit at your own risk.\n//\n//\n\nglobal string $gMainPane;\nif (`paneLayout -exists $gMainPane`) {\n\n\tglobal int $gUseScenePanelConfig;\n\tint    $useSceneConfig = $gUseScenePanelConfig;\n\tint    $nodeEditorPanelVisible = stringArrayContains(\"nodeEditorPanel1\", `getPanel -vis`);\n\tint    $nodeEditorWorkspaceControlOpen = (`workspaceControl -exists nodeEditorPanel1Window` && `workspaceControl -q -visible nodeEditorPanel1Window`);\n\tint    $menusOkayInPanels = `optionVar -q allowMenusInPanels`;\n\tint    $nVisPanes = `paneLayout -q -nvp $gMainPane`;\n\tint    $nPanes = 0;\n\tstring $editorName;\n\tstring $panelName;\n\tstring $itemFilterName;\n\tstring $panelConfig;\n\n\t//\n\t//  get current state of the UI\n\t//\n\tsceneUIReplacement -update $gMainPane;\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Top View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Top View\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"top\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 16384\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n"
		+ "            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n"
		+ "            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1\n            -height 1\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n"
		+ "\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Side View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Side View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"side\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n"
		+ "            -textureDisplay \"modulate\" \n            -textureMaxSize 16384\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n"
		+ "            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1\n            -height 1\n"
		+ "            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Front View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Front View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"front\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n"
		+ "            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 16384\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n"
		+ "            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n"
		+ "            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1\n            -height 1\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Persp View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Persp View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"persp\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n"
		+ "            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 1\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 16384\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n"
		+ "            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n"
		+ "            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1031\n            -height 1035\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"outlinerPanel\" (localizedPanelLabel(\"ToggledOutliner\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\toutlinerPanel -edit -l (localizedPanelLabel(\"ToggledOutliner\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\t$editorName = $panelName;\n        outlinerEditor -e \n            -showShapes 0\n            -showAssignedMaterials 0\n            -showTimeEditor 1\n            -showReferenceNodes 1\n            -showReferenceMembers 1\n            -showAttributes 0\n            -showConnected 0\n            -showAnimCurvesOnly 0\n            -showMuteInfo 0\n            -organizeByLayer 1\n            -organizeByClip 1\n            -showAnimLayerWeight 1\n            -autoExpandLayers 1\n            -autoExpand 0\n            -showDagOnly 1\n            -showAssets 1\n            -showContainedOnly 1\n            -showPublishedAsConnected 0\n            -showParentContainers 0\n            -showContainerContents 1\n            -ignoreDagHierarchy 0\n            -expandConnections 0\n            -showUpstreamCurves 1\n            -showUnitlessCurves 1\n            -showCompounds 1\n            -showLeafs 1\n            -showNumericAttrsOnly 0\n            -highlightActive 1\n            -autoSelectNewObjects 0\n            -doNotSelectNewObjects 0\n            -dropIsParent 1\n"
		+ "            -transmitFilters 0\n            -setFilter \"defaultSetFilter\" \n            -showSetMembers 1\n            -allowMultiSelection 1\n            -alwaysToggleSelect 0\n            -directSelect 0\n            -isSet 0\n            -isSetMember 0\n            -displayMode \"DAG\" \n            -expandObjects 0\n            -setsIgnoreFilters 1\n            -containersIgnoreFilters 0\n            -editAttrName 0\n            -showAttrValues 0\n            -highlightSecondary 0\n            -showUVAttrsOnly 0\n            -showTextureNodesOnly 0\n            -attrAlphaOrder \"default\" \n            -animLayerFilterOptions \"allAffecting\" \n            -sortOrder \"none\" \n            -longNames 0\n            -niceNames 1\n            -showNamespace 1\n            -showPinIcons 0\n            -mapMotionTrails 0\n            -ignoreHiddenAttribute 0\n            -ignoreOutlinerColor 0\n            -renderFilterVisible 0\n            -renderFilterIndex 0\n            -selectionOrder \"chronological\" \n            -expandAttribute 0\n            $editorName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"outlinerPanel\" (localizedPanelLabel(\"Outliner\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\toutlinerPanel -edit -l (localizedPanelLabel(\"Outliner\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        outlinerEditor -e \n            -showShapes 0\n            -showAssignedMaterials 0\n            -showTimeEditor 1\n            -showReferenceNodes 0\n            -showReferenceMembers 0\n            -showAttributes 0\n            -showConnected 0\n            -showAnimCurvesOnly 0\n            -showMuteInfo 0\n            -organizeByLayer 1\n            -organizeByClip 1\n            -showAnimLayerWeight 1\n            -autoExpandLayers 1\n            -autoExpand 0\n            -showDagOnly 1\n            -showAssets 1\n            -showContainedOnly 1\n            -showPublishedAsConnected 0\n            -showParentContainers 0\n            -showContainerContents 1\n            -ignoreDagHierarchy 0\n"
		+ "            -expandConnections 0\n            -showUpstreamCurves 1\n            -showUnitlessCurves 1\n            -showCompounds 1\n            -showLeafs 1\n            -showNumericAttrsOnly 0\n            -highlightActive 1\n            -autoSelectNewObjects 0\n            -doNotSelectNewObjects 0\n            -dropIsParent 1\n            -transmitFilters 0\n            -setFilter \"defaultSetFilter\" \n            -showSetMembers 1\n            -allowMultiSelection 1\n            -alwaysToggleSelect 0\n            -directSelect 0\n            -displayMode \"DAG\" \n            -expandObjects 0\n            -setsIgnoreFilters 1\n            -containersIgnoreFilters 0\n            -editAttrName 0\n            -showAttrValues 0\n            -highlightSecondary 0\n            -showUVAttrsOnly 0\n            -showTextureNodesOnly 0\n            -attrAlphaOrder \"default\" \n            -animLayerFilterOptions \"allAffecting\" \n            -sortOrder \"none\" \n            -longNames 0\n            -niceNames 1\n            -showNamespace 1\n            -showPinIcons 0\n"
		+ "            -mapMotionTrails 0\n            -ignoreHiddenAttribute 0\n            -ignoreOutlinerColor 0\n            -renderFilterVisible 0\n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"graphEditor\" (localizedPanelLabel(\"Graph Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Graph Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"OutlineEd\");\n            outlinerEditor -e \n                -showShapes 1\n                -showAssignedMaterials 0\n                -showTimeEditor 1\n                -showReferenceNodes 0\n                -showReferenceMembers 0\n                -showAttributes 1\n                -showConnected 1\n                -showAnimCurvesOnly 1\n                -showMuteInfo 0\n                -organizeByLayer 1\n                -organizeByClip 1\n                -showAnimLayerWeight 1\n                -autoExpandLayers 1\n"
		+ "                -autoExpand 1\n                -showDagOnly 0\n                -showAssets 1\n                -showContainedOnly 0\n                -showPublishedAsConnected 0\n                -showParentContainers 1\n                -showContainerContents 0\n                -ignoreDagHierarchy 0\n                -expandConnections 1\n                -showUpstreamCurves 1\n                -showUnitlessCurves 1\n                -showCompounds 0\n                -showLeafs 1\n                -showNumericAttrsOnly 1\n                -highlightActive 0\n                -autoSelectNewObjects 1\n                -doNotSelectNewObjects 0\n                -dropIsParent 1\n                -transmitFilters 1\n                -setFilter \"0\" \n                -showSetMembers 0\n                -allowMultiSelection 1\n                -alwaysToggleSelect 0\n                -directSelect 0\n                -displayMode \"DAG\" \n                -expandObjects 0\n                -setsIgnoreFilters 1\n                -containersIgnoreFilters 0\n                -editAttrName 0\n"
		+ "                -showAttrValues 0\n                -highlightSecondary 0\n                -showUVAttrsOnly 0\n                -showTextureNodesOnly 0\n                -attrAlphaOrder \"default\" \n                -animLayerFilterOptions \"allAffecting\" \n                -sortOrder \"none\" \n                -longNames 0\n                -niceNames 1\n                -showNamespace 1\n                -showPinIcons 1\n                -mapMotionTrails 1\n                -ignoreHiddenAttribute 0\n                -ignoreOutlinerColor 0\n                -renderFilterVisible 0\n                $editorName;\n\n\t\t\t$editorName = ($panelName+\"GraphEd\");\n            animCurveEditor -e \n                -displayKeys 1\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 1\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 1\n                -snapTime \"integer\" \n                -snapValue \"none\" \n                -showResults \"off\" \n                -showBufferCurves \"off\" \n"
		+ "                -smoothness \"fine\" \n                -resultSamples 1.25\n                -resultScreenSamples 0\n                -resultUpdate \"delayed\" \n                -showUpstreamCurves 1\n                -showCurveNames 0\n                -showActiveCurveNames 0\n                -stackedCurves 0\n                -stackedCurvesMin -1\n                -stackedCurvesMax 1\n                -stackedCurvesSpace 0.2\n                -displayNormalized 0\n                -preSelectionHighlight 0\n                -constrainDrag 0\n                -classicMode 1\n                -valueLinesToggle 1\n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dopeSheetPanel\" (localizedPanelLabel(\"Dope Sheet\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Dope Sheet\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"OutlineEd\");\n            outlinerEditor -e \n"
		+ "                -showShapes 1\n                -showAssignedMaterials 0\n                -showTimeEditor 1\n                -showReferenceNodes 0\n                -showReferenceMembers 0\n                -showAttributes 1\n                -showConnected 1\n                -showAnimCurvesOnly 1\n                -showMuteInfo 0\n                -organizeByLayer 1\n                -organizeByClip 1\n                -showAnimLayerWeight 1\n                -autoExpandLayers 1\n                -autoExpand 0\n                -showDagOnly 0\n                -showAssets 1\n                -showContainedOnly 0\n                -showPublishedAsConnected 0\n                -showParentContainers 1\n                -showContainerContents 0\n                -ignoreDagHierarchy 0\n                -expandConnections 1\n                -showUpstreamCurves 1\n                -showUnitlessCurves 0\n                -showCompounds 1\n                -showLeafs 1\n                -showNumericAttrsOnly 1\n                -highlightActive 0\n                -autoSelectNewObjects 0\n"
		+ "                -doNotSelectNewObjects 1\n                -dropIsParent 1\n                -transmitFilters 0\n                -setFilter \"0\" \n                -showSetMembers 0\n                -allowMultiSelection 1\n                -alwaysToggleSelect 0\n                -directSelect 0\n                -displayMode \"DAG\" \n                -expandObjects 0\n                -setsIgnoreFilters 1\n                -containersIgnoreFilters 0\n                -editAttrName 0\n                -showAttrValues 0\n                -highlightSecondary 0\n                -showUVAttrsOnly 0\n                -showTextureNodesOnly 0\n                -attrAlphaOrder \"default\" \n                -animLayerFilterOptions \"allAffecting\" \n                -sortOrder \"none\" \n                -longNames 0\n                -niceNames 1\n                -showNamespace 1\n                -showPinIcons 0\n                -mapMotionTrails 1\n                -ignoreHiddenAttribute 0\n                -ignoreOutlinerColor 0\n                -renderFilterVisible 0\n                $editorName;\n"
		+ "\n\t\t\t$editorName = ($panelName+\"DopeSheetEd\");\n            dopeSheetEditor -e \n                -displayKeys 1\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 0\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 0\n                -snapTime \"integer\" \n                -snapValue \"none\" \n                -outliner \"dopeSheetPanel1OutlineEd\" \n                -showSummary 1\n                -showScene 0\n                -hierarchyBelow 0\n                -showTicks 1\n                -selectionWindow 0 0 0 0 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"timeEditorPanel\" (localizedPanelLabel(\"Time Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Time Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n"
		+ "\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"clipEditorPanel\" (localizedPanelLabel(\"Trax Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Trax Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = clipEditorNameFromPanel($panelName);\n            clipEditor -e \n                -displayKeys 0\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 0\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 0\n                -snapTime \"none\" \n                -snapValue \"none\" \n                -initialized 0\n                -manageSequencer 0 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"sequenceEditorPanel\" (localizedPanelLabel(\"Camera Sequencer\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n"
		+ "\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Camera Sequencer\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = sequenceEditorNameFromPanel($panelName);\n            clipEditor -e \n                -displayKeys 0\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 0\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 0\n                -snapTime \"none\" \n                -snapValue \"none\" \n                -initialized 0\n                -manageSequencer 1 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"hyperGraphPanel\" (localizedPanelLabel(\"Hypergraph Hierarchy\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Hypergraph Hierarchy\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"HyperGraphEd\");\n            hyperGraph -e \n"
		+ "                -graphLayoutStyle \"hierarchicalLayout\" \n                -orientation \"horiz\" \n                -mergeConnections 0\n                -zoom 1\n                -animateTransition 0\n                -showRelationships 1\n                -showShapes 0\n                -showDeformers 0\n                -showExpressions 0\n                -showConstraints 0\n                -showConnectionFromSelected 0\n                -showConnectionToSelected 0\n                -showConstraintLabels 0\n                -showUnderworld 0\n                -showInvisible 0\n                -transitionFrames 1\n                -opaqueContainers 0\n                -freeform 0\n                -imagePosition 0 0 \n                -imageScale 1\n                -imageEnabled 0\n                -graphType \"DAG\" \n                -heatMapDisplay 0\n                -updateSelection 1\n                -updateNodeAdded 1\n                -useDrawOverrideColor 0\n                -limitGraphTraversal -1\n                -range 0 0 \n                -iconSize \"smallIcons\" \n"
		+ "                -showCachedConnections 0\n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"hyperShadePanel\" (localizedPanelLabel(\"Hypershade\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Hypershade\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"visorPanel\" (localizedPanelLabel(\"Visor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Visor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"nodeEditorPanel\" (localizedPanelLabel(\"Node Editor\")) `;\n\tif ($nodeEditorPanelVisible || $nodeEditorWorkspaceControlOpen) {\n\t\tif (\"\" == $panelName) {\n\t\t\tif ($useSceneConfig) {\n"
		+ "\t\t\t\t$panelName = `scriptedPanel -unParent  -type \"nodeEditorPanel\" -l (localizedPanelLabel(\"Node Editor\")) -mbv $menusOkayInPanels `;\n\n\t\t\t$editorName = ($panelName+\"NodeEditorEd\");\n            nodeEditor -e \n                -allAttributes 0\n                -allNodes 0\n                -autoSizeNodes 1\n                -consistentNameSize 1\n                -createNodeCommand \"nodeEdCreateNodeCommand\" \n                -connectNodeOnCreation 0\n                -connectOnDrop 0\n                -copyConnectionsOnPaste 0\n                -defaultPinnedState 0\n                -additiveGraphingMode 0\n                -settingsChangedCallback \"nodeEdSyncControls\" \n                -traversalDepthLimit -1\n                -keyPressCommand \"nodeEdKeyPressCommand\" \n                -nodeTitleMode \"name\" \n                -gridSnap 0\n                -gridVisibility 1\n                -crosshairOnEdgeDragging 0\n                -popupMenuScript \"nodeEdBuildPanelMenus\" \n                -showNamespace 1\n                -showShapes 1\n                -showSGShapes 0\n"
		+ "                -showTransforms 1\n                -useAssets 1\n                -syncedSelection 1\n                -extendToShapes 1\n                -editorMode \"default\" \n                $editorName;\n\t\t\t}\n\t\t} else {\n\t\t\t$label = `panel -q -label $panelName`;\n\t\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Node Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"NodeEditorEd\");\n            nodeEditor -e \n                -allAttributes 0\n                -allNodes 0\n                -autoSizeNodes 1\n                -consistentNameSize 1\n                -createNodeCommand \"nodeEdCreateNodeCommand\" \n                -connectNodeOnCreation 0\n                -connectOnDrop 0\n                -copyConnectionsOnPaste 0\n                -defaultPinnedState 0\n                -additiveGraphingMode 0\n                -settingsChangedCallback \"nodeEdSyncControls\" \n                -traversalDepthLimit -1\n                -keyPressCommand \"nodeEdKeyPressCommand\" \n                -nodeTitleMode \"name\" \n                -gridSnap 0\n"
		+ "                -gridVisibility 1\n                -crosshairOnEdgeDragging 0\n                -popupMenuScript \"nodeEdBuildPanelMenus\" \n                -showNamespace 1\n                -showShapes 1\n                -showSGShapes 0\n                -showTransforms 1\n                -useAssets 1\n                -syncedSelection 1\n                -extendToShapes 1\n                -editorMode \"default\" \n                $editorName;\n\t\t\tif (!$useSceneConfig) {\n\t\t\t\tpanel -e -l $label $panelName;\n\t\t\t}\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"createNodePanel\" (localizedPanelLabel(\"Create Node\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Create Node\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"polyTexturePlacementPanel\" (localizedPanelLabel(\"UV Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n"
		+ "\t\tscriptedPanel -edit -l (localizedPanelLabel(\"UV Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"renderWindowPanel\" (localizedPanelLabel(\"Render View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Render View\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"shapePanel\" (localizedPanelLabel(\"Shape Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tshapePanel -edit -l (localizedPanelLabel(\"Shape Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"posePanel\" (localizedPanelLabel(\"Pose Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tposePanel -edit -l (localizedPanelLabel(\"Pose Editor\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dynRelEdPanel\" (localizedPanelLabel(\"Dynamic Relationships\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Dynamic Relationships\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"relationshipPanel\" (localizedPanelLabel(\"Relationship Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Relationship Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"referenceEditorPanel\" (localizedPanelLabel(\"Reference Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Reference Editor\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"componentEditorPanel\" (localizedPanelLabel(\"Component Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Component Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dynPaintScriptedPanelType\" (localizedPanelLabel(\"Paint Effects\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Paint Effects\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"scriptEditorPanel\" (localizedPanelLabel(\"Script Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Script Editor\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"profilerPanel\" (localizedPanelLabel(\"Profiler Tool\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Profiler Tool\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"contentBrowserPanel\" (localizedPanelLabel(\"Content Browser\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Content Browser\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"Stereo\" (localizedPanelLabel(\"Stereo\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Stereo\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "string $editorName = ($panelName+\"Editor\");\n            stereoCameraView -e \n                -camera \"persp\" \n                -useInteractiveMode 0\n                -displayLights \"default\" \n                -displayAppearance \"wireframe\" \n                -activeOnly 0\n                -ignorePanZoom 0\n                -wireframeOnShaded 0\n                -headsUpDisplay 1\n                -holdOuts 1\n                -selectionHiliteDisplay 1\n                -useDefaultMaterial 0\n                -bufferMode \"double\" \n                -twoSidedLighting 1\n                -backfaceCulling 0\n                -xray 0\n                -jointXray 0\n                -activeComponentsXray 0\n                -displayTextures 0\n                -smoothWireframe 0\n                -lineWidth 1\n                -textureAnisotropic 0\n                -textureHilight 1\n                -textureSampling 2\n                -textureDisplay \"modulate\" \n                -textureMaxSize 16384\n                -fogging 0\n                -fogSource \"fragment\" \n"
		+ "                -fogMode \"linear\" \n                -fogStart 0\n                -fogEnd 100\n                -fogDensity 0.1\n                -fogColor 0.5 0.5 0.5 1 \n                -depthOfFieldPreview 1\n                -maxConstantTransparency 1\n                -objectFilterShowInHUD 1\n                -isFiltered 0\n                -colorResolution 4 4 \n                -bumpResolution 4 4 \n                -textureCompression 0\n                -transparencyAlgorithm \"frontAndBackCull\" \n                -transpInShadows 0\n                -cullingOverride \"none\" \n                -lowQualityLighting 0\n                -maximumNumHardwareLights 0\n                -occlusionCulling 0\n                -shadingModel 0\n                -useBaseRenderer 0\n                -useReducedRenderer 0\n                -smallObjectCulling 0\n                -smallObjectThreshold -1 \n                -interactiveDisableShadows 0\n                -interactiveBackFaceCull 0\n                -sortTransparent 1\n                -controllers 1\n                -nurbsCurves 1\n"
		+ "                -nurbsSurfaces 1\n                -polymeshes 1\n                -subdivSurfaces 1\n                -planes 1\n                -lights 1\n                -cameras 1\n                -controlVertices 1\n                -hulls 1\n                -grid 1\n                -imagePlane 1\n                -joints 1\n                -ikHandles 1\n                -deformers 1\n                -dynamics 1\n                -particleInstancers 1\n                -fluids 1\n                -hairSystems 1\n                -follicles 1\n                -nCloths 1\n                -nParticles 1\n                -nRigids 1\n                -dynamicConstraints 1\n                -locators 1\n                -manipulators 1\n                -pluginShapes 1\n                -dimensions 1\n                -handles 1\n                -pivots 1\n                -textures 1\n                -strokes 1\n                -motionTrails 1\n                -clipGhosts 1\n                -greasePencils 1\n                -shadows 0\n                -captureSequenceNumber -1\n"
		+ "                -width 0\n                -height 0\n                -sceneRenderFilter 0\n                -displayMode \"centerEye\" \n                -viewColor 0 0 0 1 \n                -useCustomBackground 1\n                $editorName;\n            stereoCameraView -e -viewSelected 0 $editorName;\n            stereoCameraView -e \n                -pluginObjects \"gpuCacheDisplayFilter\" 1 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\tif ($useSceneConfig) {\n        string $configName = `getPanel -cwl (localizedPanelLabel(\"Current Layout\"))`;\n        if (\"\" != $configName) {\n\t\t\tpanelConfiguration -edit -label (localizedPanelLabel(\"Current Layout\")) \n\t\t\t\t-userCreated false\n\t\t\t\t-defaultImage \"\"\n\t\t\t\t-image \"\"\n\t\t\t\t-sc false\n\t\t\t\t-configString \"global string $gMainPane; paneLayout -e -cn \\\"single\\\" -ps 1 100 100 $gMainPane;\"\n\t\t\t\t-removeAllPanels\n\t\t\t\t-ap false\n\t\t\t\t\t(localizedPanelLabel(\"Persp View\")) \n\t\t\t\t\t\"modelPanel\"\n"
		+ "\t\t\t\t\t\"$panelName = `modelPanel -unParent -l (localizedPanelLabel(\\\"Persp View\\\")) -mbv $menusOkayInPanels `;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera persp` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 1\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 16384\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 1\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 1031\\n    -height 1035\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t\t\"modelPanel -edit -l (localizedPanelLabel(\\\"Persp View\\\")) -mbv $menusOkayInPanels  $panelName;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera persp` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 1\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 16384\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 1\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 1031\\n    -height 1035\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t$configName;\n\n            setNamedPanelLayout (localizedPanelLabel(\"Current Layout\"));\n        }\n\n        panelHistory -e -clear mainPanelHistory;\n        sceneUIReplacement -clear;\n\t}\n\n\ngrid -spacing 5 -size 12 -divisions 5 -displayAxes yes -displayGridLines yes -displayDivisionLines yes -displayPerspectiveLabels no -displayOrthographicLabels no -displayAxesBold yes -perspectiveLabelPosition axis -orthographicLabelPosition edge;\nviewManip -drawCompass 0 -compassAngle 0 -frontParameters \"\" -homeParameters \"\" -selectionLockParameters \"\";\n}\n");
	setAttr ".st" 3;
createNode animCurveTL -n "locator5_translateX";
	rename -uid "1094EC61-41DC-F644-9BE2-F2ADC1527DC2";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr ".ktv[0]"  0 0;
createNode animCurveTL -n "locator5_translateY";
	rename -uid "FF852B8A-4C6F-493B-076A-CBA0120831CD";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr ".ktv[0]"  0 12;
createNode animCurveTL -n "locator5_translateZ";
	rename -uid "4BB6D60E-4721-376D-7A70-3E908F0F7EE9";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr ".ktv[0]"  0 0;
createNode animCurveTU -n "locator2_scaleX";
	rename -uid "C4042269-43EF-C44C-87E3-C5824EBBD9E7";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  85 1 118 1;
createNode animCurveTU -n "locator2_scaleY";
	rename -uid "847AEE48-455E-0B61-FE9B-4D9F6D99B95B";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  85 1 118 1;
createNode animCurveTU -n "locator2_scaleZ";
	rename -uid "951F58CE-4897-A723-EDFD-D7810FEF5ECF";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  85 1 118 6.3346775823407171;
createNode animCurveTU -n "locator3_scaleX";
	rename -uid "44DA5986-4AC1-32E1-4868-9B8C2A8C6FF9";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  85 1 113 8.9903892845441007;
createNode animCurveTU -n "locator3_scaleY";
	rename -uid "5785BE4E-40CD-396A-F698-359FC7F38624";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  85 1 113 0.62873761107098591;
createNode animCurveTU -n "locator3_scaleZ";
	rename -uid "3EC51781-4166-007D-2E84-8D8C851A397D";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  85 1 113 6.7275535158939643;
createNode animCurveTA -n "locator3_rotateX";
	rename -uid "4AD16252-4837-3D2C-7724-569218381927";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  113 0 153 0;
createNode animCurveTA -n "locator3_rotateY";
	rename -uid "C7A4659F-4ED9-0680-19D8-04BE0307093E";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  113 0 153 -51.95551330890747;
createNode animCurveTA -n "locator3_rotateZ";
	rename -uid "FE15B52B-48FB-3ED0-8E9E-01B6BD410D2F";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  113 0 153 0;
createNode animCurveTA -n "locator2_rotateX";
	rename -uid "620E6101-47FE-8E48-AFE6-748B7527DCA0";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  113 0 153 0;
createNode animCurveTA -n "locator2_rotateY";
	rename -uid "9BFFA41C-4298-388C-B4EB-3097EFA5A847";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  113 0 153 -51.95551330890747;
createNode animCurveTA -n "locator2_rotateZ";
	rename -uid "0A9FDED1-405C-7785-44E1-97B214DE4C27";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  113 0 153 0;
select -ne :time1;
	setAttr -av -k on ".cch";
	setAttr -av -cb on ".ihi";
	setAttr -av -k on ".nds";
	setAttr -cb on ".bnm";
	setAttr -k on ".o" 0;
	setAttr -av ".unw";
	setAttr -k on ".etw";
	setAttr -k on ".tps";
	setAttr -av -k on ".tms";
select -ne :hardwareRenderingGlobals;
	setAttr ".etmr" no;
	setAttr ".tmr" 4096;
select -ne :renderPartition;
	setAttr -k on ".cch";
	setAttr -cb on ".ihi";
	setAttr -k on ".nds";
	setAttr -cb on ".bnm";
	setAttr -s 2 ".st";
	setAttr -cb on ".an";
	setAttr -cb on ".pt";
select -ne :renderGlobalsList1;
	setAttr -k on ".cch";
	setAttr -cb on ".ihi";
	setAttr -k on ".nds";
	setAttr -cb on ".bnm";
select -ne :defaultShaderList1;
	setAttr -k on ".cch";
	setAttr -cb on ".ihi";
	setAttr -k on ".nds";
	setAttr -cb on ".bnm";
	setAttr -s 4 ".s";
select -ne :postProcessList1;
	setAttr -k on ".cch";
	setAttr -cb on ".ihi";
	setAttr -k on ".nds";
	setAttr -cb on ".bnm";
	setAttr -s 2 ".p";
select -ne :defaultRenderingList1;
	setAttr -k on ".ihi";
select -ne :initialShadingGroup;
	setAttr -av -k on ".cch";
	setAttr -cb on ".ihi";
	setAttr -av -k on ".nds";
	setAttr -cb on ".bnm";
	setAttr -s 11 ".dsm";
	setAttr -k on ".mwc";
	setAttr -cb on ".an";
	setAttr -cb on ".il";
	setAttr -cb on ".vo";
	setAttr -cb on ".eo";
	setAttr -cb on ".fo";
	setAttr -cb on ".epo";
	setAttr -k on ".ro";
connectAttr "cluster5.og[0]" "curveShape1.cr";
connectAttr "tweak1.pl[0].cp[0]" "curveShape1.twl";
connectAttr "cluster1GroupId.id" "curveShape1.iog.og[0].gid";
connectAttr "cluster1Set.mwc" "curveShape1.iog.og[0].gco";
connectAttr "groupId2.id" "curveShape1.iog.og[1].gid";
connectAttr "tweakSet1.mwc" "curveShape1.iog.og[1].gco";
connectAttr "cluster2GroupId.id" "curveShape1.iog.og[2].gid";
connectAttr "cluster2Set.mwc" "curveShape1.iog.og[2].gco";
connectAttr "cluster3GroupId.id" "curveShape1.iog.og[3].gid";
connectAttr "cluster3Set.mwc" "curveShape1.iog.og[3].gco";
connectAttr "cluster4GroupId.id" "curveShape1.iog.og[4].gid";
connectAttr "cluster4Set.mwc" "curveShape1.iog.og[4].gco";
connectAttr "cluster5GroupId.id" "curveShape1.iog.og[5].gid";
connectAttr "cluster5Set.mwc" "curveShape1.iog.og[5].gco";
connectAttr "locator1_translateX.o" "locator1.tx";
connectAttr "locator1_translateY.o" "locator1.ty";
connectAttr "locator1_translateZ.o" "locator1.tz";
connectAttr "locator2_translateX.o" "locator2.tx";
connectAttr "locator2_translateY.o" "locator2.ty";
connectAttr "locator2_translateZ.o" "locator2.tz";
connectAttr "locator2_scaleX.o" "locator2.sx";
connectAttr "locator2_scaleY.o" "locator2.sy";
connectAttr "locator2_scaleZ.o" "locator2.sz";
connectAttr "locator2_rotateX.o" "locator2.rx";
connectAttr "locator2_rotateY.o" "locator2.ry";
connectAttr "locator2_rotateZ.o" "locator2.rz";
connectAttr "locator3_translateX.o" "locator3.tx";
connectAttr "locator3_translateY.o" "locator3.ty";
connectAttr "locator3_translateZ.o" "locator3.tz";
connectAttr "locator3_scaleX.o" "locator3.sx";
connectAttr "locator3_scaleY.o" "locator3.sy";
connectAttr "locator3_scaleZ.o" "locator3.sz";
connectAttr "locator3_rotateX.o" "locator3.rx";
connectAttr "locator3_rotateY.o" "locator3.ry";
connectAttr "locator3_rotateZ.o" "locator3.rz";
connectAttr "locator4_translateX.o" "locator4.tx";
connectAttr "locator4_translateY.o" "locator4.ty";
connectAttr "locator4_translateZ.o" "locator4.tz";
connectAttr "locator5_translateX.o" "locator5.tx";
connectAttr "locator5_translateY.o" "locator5.ty";
connectAttr "locator5_translateZ.o" "locator5.tz";
connectAttr "pCube1_u.o" "pCube1.u";
connectAttr "spineNode.outputTranslate[0]" "pCube1.t";
connectAttr "spineNode.outputScale[0]" "pCube1.s";
connectAttr "spineNode.outputRotate[0]" "pCube1.r";
connectAttr "polyCube1.out" "pCubeShape1.i";
connectAttr "pCube2_u.o" "pCube2.u";
connectAttr "spineNode.outputTranslate[1]" "pCube2.t";
connectAttr "spineNode.outputScale[1]" "pCube2.s";
connectAttr "spineNode.outputRotate[1]" "pCube2.r";
connectAttr "pCube3_u.o" "pCube3.u";
connectAttr "spineNode.outputTranslate[2]" "pCube3.t";
connectAttr "spineNode.outputScale[2]" "pCube3.s";
connectAttr "spineNode.outputRotate[2]" "pCube3.r";
connectAttr "pCube4_u.o" "pCube4.u";
connectAttr "spineNode.outputTranslate[3]" "pCube4.t";
connectAttr "spineNode.outputScale[3]" "pCube4.s";
connectAttr "spineNode.outputRotate[3]" "pCube4.r";
connectAttr "pCube5_u.o" "pCube5.u";
connectAttr "spineNode.outputTranslate[4]" "pCube5.t";
connectAttr "spineNode.outputScale[4]" "pCube5.s";
connectAttr "spineNode.outputRotate[4]" "pCube5.r";
connectAttr "pCube6_u.o" "pCube6.u";
connectAttr "spineNode.outputTranslate[5]" "pCube6.t";
connectAttr "spineNode.outputScale[5]" "pCube6.s";
connectAttr "spineNode.outputRotate[5]" "pCube6.r";
connectAttr "pCube7_u.o" "pCube7.u";
connectAttr "spineNode.outputTranslate[6]" "pCube7.t";
connectAttr "spineNode.outputScale[6]" "pCube7.s";
connectAttr "spineNode.outputRotate[6]" "pCube7.r";
connectAttr "pCube8_u.o" "pCube8.u";
connectAttr "spineNode.outputTranslate[7]" "pCube8.t";
connectAttr "spineNode.outputScale[7]" "pCube8.s";
connectAttr "spineNode.outputRotate[7]" "pCube8.r";
connectAttr "pCube9_u.o" "pCube9.u";
connectAttr "spineNode.outputTranslate[8]" "pCube9.t";
connectAttr "spineNode.outputScale[8]" "pCube9.s";
connectAttr "spineNode.outputRotate[8]" "pCube9.r";
connectAttr "pCube10_u.o" "pCube10.u";
connectAttr "spineNode.outputTranslate[9]" "pCube10.t";
connectAttr "spineNode.outputScale[9]" "pCube10.s";
connectAttr "spineNode.outputRotate[9]" "pCube10.r";
connectAttr "pCube11_u.o" "pCube11.u";
connectAttr "spineNode.outputTranslate[10]" "pCube11.t";
connectAttr "spineNode.outputScale[10]" "pCube11.s";
connectAttr "spineNode.outputRotate[10]" "pCube11.r";
relationship "link" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "link" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
connectAttr "layerManager.dli[0]" "defaultLayer.id";
connectAttr "renderLayerManager.rlmi[0]" "defaultRenderLayer.rlid";
connectAttr "cluster1GroupParts.og" "cluster1.ip[0].ig";
connectAttr "cluster1GroupId.id" "cluster1.ip[0].gi";
connectAttr "cluster1Handle.wm" "cluster1.ma";
connectAttr "cluster1HandleShape.x" "cluster1.x";
connectAttr "groupParts2.og" "tweak1.ip[0].ig";
connectAttr "groupId2.id" "tweak1.ip[0].gi";
connectAttr "cluster1GroupId.msg" "cluster1Set.gn" -na;
connectAttr "curveShape1.iog.og[0]" "cluster1Set.dsm" -na;
connectAttr "cluster1.msg" "cluster1Set.ub[0]";
connectAttr "tweak1.og[0]" "cluster1GroupParts.ig";
connectAttr "cluster1GroupId.id" "cluster1GroupParts.gi";
connectAttr "groupId2.msg" "tweakSet1.gn" -na;
connectAttr "curveShape1.iog.og[1]" "tweakSet1.dsm" -na;
connectAttr "tweak1.msg" "tweakSet1.ub[0]";
connectAttr "curveShape1Orig.ws" "groupParts2.ig";
connectAttr "groupId2.id" "groupParts2.gi";
connectAttr "cluster2GroupParts.og" "cluster2.ip[0].ig";
connectAttr "cluster2GroupId.id" "cluster2.ip[0].gi";
connectAttr "cluster2Handle.wm" "cluster2.ma";
connectAttr "cluster2HandleShape.x" "cluster2.x";
connectAttr "cluster2GroupId.msg" "cluster2Set.gn" -na;
connectAttr "curveShape1.iog.og[2]" "cluster2Set.dsm" -na;
connectAttr "cluster2.msg" "cluster2Set.ub[0]";
connectAttr "cluster1.og[0]" "cluster2GroupParts.ig";
connectAttr "cluster2GroupId.id" "cluster2GroupParts.gi";
connectAttr "cluster3GroupParts.og" "cluster3.ip[0].ig";
connectAttr "cluster3GroupId.id" "cluster3.ip[0].gi";
connectAttr "cluster3Handle.wm" "cluster3.ma";
connectAttr "cluster3HandleShape.x" "cluster3.x";
connectAttr "cluster3GroupId.msg" "cluster3Set.gn" -na;
connectAttr "curveShape1.iog.og[3]" "cluster3Set.dsm" -na;
connectAttr "cluster3.msg" "cluster3Set.ub[0]";
connectAttr "cluster2.og[0]" "cluster3GroupParts.ig";
connectAttr "cluster3GroupId.id" "cluster3GroupParts.gi";
connectAttr "cluster4GroupParts.og" "cluster4.ip[0].ig";
connectAttr "cluster4GroupId.id" "cluster4.ip[0].gi";
connectAttr "cluster4Handle.wm" "cluster4.ma";
connectAttr "cluster4HandleShape.x" "cluster4.x";
connectAttr "cluster4GroupId.msg" "cluster4Set.gn" -na;
connectAttr "curveShape1.iog.og[4]" "cluster4Set.dsm" -na;
connectAttr "cluster4.msg" "cluster4Set.ub[0]";
connectAttr "cluster3.og[0]" "cluster4GroupParts.ig";
connectAttr "cluster4GroupId.id" "cluster4GroupParts.gi";
connectAttr "cluster5GroupParts.og" "cluster5.ip[0].ig";
connectAttr "cluster5GroupId.id" "cluster5.ip[0].gi";
connectAttr "cluster5Handle.wm" "cluster5.ma";
connectAttr "cluster5HandleShape.x" "cluster5.x";
connectAttr "cluster5GroupId.msg" "cluster5Set.gn" -na;
connectAttr "curveShape1.iog.og[5]" "cluster5Set.dsm" -na;
connectAttr "cluster5.msg" "cluster5Set.ub[0]";
connectAttr "cluster4.og[0]" "cluster5GroupParts.ig";
connectAttr "cluster5GroupId.id" "cluster5GroupParts.gi";
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
connectAttr "curveShape1.ws" "spineNode.inputCurve";
connectAttr "locatorShape1.wm" "spineNode.controlMatrices[0]";
connectAttr "locatorShape2.wm" "spineNode.controlMatrices[1]";
connectAttr "locatorShape3.wm" "spineNode.controlMatrices[2]";
connectAttr "locatorShape4.wm" "spineNode.controlMatrices[3]";
connectAttr "locatorShape5.wm" "spineNode.controlMatrices[4]";
connectAttr "defaultRenderLayer.msg" ":defaultRenderingList1.r" -na;
connectAttr "pCubeShape1.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pCubeShape2.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pCubeShape3.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pCubeShape4.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pCubeShape5.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pCubeShape6.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pCubeShape7.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pCubeShape8.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pCubeShape9.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pCubeShape10.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pCubeShape11.iog" ":initialShadingGroup.dsm" -na;
// End of quaternionSpineNode.ma
