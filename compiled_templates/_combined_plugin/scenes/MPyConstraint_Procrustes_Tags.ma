//Maya ASCII 2026 scene
//Name: MPyConstraint_Procrustes_Tags.ma
//Last modified: Tue, Aug 25, 2026 12:18:40 PM
//Codeset: UTF-8
requires maya "2026";
requires -nodeType "procrustesTags" "mPyMega" "1.0";
currentUnit -l centimeter -a degree -t film;
fileInfo "application" "maya";
fileInfo "product" "Maya 2026";
fileInfo "version" "2026";
fileInfo "cutIdentifier" "202510291147-60ec9eda33";
fileInfo "osv" "Mac OS X 20.6.2";
fileInfo "UUID" "56F8307D-0542-D83D-D162-D18FE29562AC";
createNode transform -s -n "persp";
	rename -uid "581CE7F4-F844-489D-CBA7-169E548DCA90";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 28 21 28 ;
	setAttr ".r" -type "double3" -27.938352729602379 44.999999999999972 -5.172681101354183e-14 ;
createNode camera -s -n "perspShape" -p "persp";
	rename -uid "0CAEE320-3C49-4CF6-386A-ED84A7DA4B79";
	setAttr -k off ".v" no;
	setAttr ".fl" 34.999999999999993;
	setAttr ".coi" 44.82186966202994;
	setAttr ".imn" -type "string" "persp";
	setAttr ".den" -type "string" "persp_depth";
	setAttr ".man" -type "string" "persp_mask";
	setAttr ".hc" -type "string" "viewSet -p %camera";
createNode transform -s -n "top";
	rename -uid "20C63520-6547-88A0-461E-8FBC80DF7BAE";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 0 1000.1 0 ;
	setAttr ".r" -type "double3" -89.999999999999986 0 0 ;
createNode camera -s -n "topShape" -p "top";
	rename -uid "502C1232-4449-BCDB-52BE-968EFF3BBB20";
	setAttr -k off ".v" no;
	setAttr ".rnd" no;
	setAttr ".coi" 1000.1;
	setAttr ".ow" 30;
	setAttr ".imn" -type "string" "top";
	setAttr ".den" -type "string" "top_depth";
	setAttr ".man" -type "string" "top_mask";
	setAttr ".hc" -type "string" "viewSet -t %camera";
	setAttr ".o" yes;
createNode transform -s -n "front";
	rename -uid "7A88C123-0A4D-0FE5-6862-2286234A00AE";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 0 0 1000.1 ;
createNode camera -s -n "frontShape" -p "front";
	rename -uid "99BDE12E-6E44-13DB-08D2-D0953EFCFB14";
	setAttr -k off ".v" no;
	setAttr ".rnd" no;
	setAttr ".coi" 1000.1;
	setAttr ".ow" 30;
	setAttr ".imn" -type "string" "front";
	setAttr ".den" -type "string" "front_depth";
	setAttr ".man" -type "string" "front_mask";
	setAttr ".hc" -type "string" "viewSet -f %camera";
	setAttr ".o" yes;
createNode transform -s -n "side";
	rename -uid "3F7DDE2D-A141-0DE4-C656-A98DBC5B6702";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 1000.1 0 0 ;
	setAttr ".r" -type "double3" 0 89.999999999999986 0 ;
createNode camera -s -n "sideShape" -p "side";
	rename -uid "C1D5D7EA-3F49-7372-F770-4196FABDB204";
	setAttr -k off ".v" no;
	setAttr ".rnd" no;
	setAttr ".coi" 1000.1;
	setAttr ".ow" 30;
	setAttr ".imn" -type "string" "side";
	setAttr ".den" -type "string" "side_depth";
	setAttr ".man" -type "string" "side_mask";
	setAttr ".hc" -type "string" "viewSet -s %camera";
	setAttr ".o" yes;
createNode transform -n "twistTube";
	rename -uid "D79C1CAD-6543-5F04-38AC-4A81C6154A54";
createNode mesh -n "twistTubeShape" -p "twistTube";
	rename -uid "3452EB45-CF4E-A8B8-1339-03AD2EE42097";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr ".ndt" 0;
createNode mesh -n "twistTubeShapeOrig" -p "twistTube";
	rename -uid "4DDBA17F-F844-D712-0F8E-C0B063D51A29";
	setAttr -k off ".v";
	setAttr ".io" yes;
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr -s 5 ".gtag";
	setAttr ".gtag[0].gtagnm" -type "string" "ring0";
	setAttr ".gtag[0].gtagcmp" -type "componentList" 1 "vtx[32:63]";
	setAttr ".gtag[1].gtagnm" -type "string" "ring1";
	setAttr ".gtag[1].gtagcmp" -type "componentList" 1 "vtx[80:95]";
	setAttr ".gtag[2].gtagnm" -type "string" "ring2";
	setAttr ".gtag[2].gtagcmp" -type "componentList" 1 "vtx[112:143]";
	setAttr ".gtag[3].gtagnm" -type "string" "ring3";
	setAttr ".gtag[3].gtagcmp" -type "componentList" 1 "vtx[160:191]";
	setAttr ".gtag[4].gtagnm" -type "string" "ringAlt";
	setAttr ".gtag[4].gtagcmp" -type "componentList" 1 "vtx[64:79]";
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr ".ndt" 0;
createNode transform -n "twistTube_rest";
	rename -uid "CF0A9453-D148-F8C9-2689-59A2F30A96E7";
createNode mesh -n "twistTube_restShape" -p "twistTube_rest";
	rename -uid "78D2135F-674D-DAF3-DB04-7EA2DC783838";
	setAttr -k off ".v";
	setAttr ".io" yes;
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr -s 10 ".gtag";
	setAttr ".gtag[0].gtagnm" -type "string" "bottom";
	setAttr ".gtag[0].gtagcmp" -type "componentList" 1 "f[192]";
	setAttr ".gtag[1].gtagnm" -type "string" "bottomRing";
	setAttr ".gtag[1].gtagcmp" -type "componentList" 1 "e[0:15]";
	setAttr ".gtag[2].gtagnm" -type "string" "cylBottomCap";
	setAttr ".gtag[2].gtagcmp" -type "componentList" 1 "vtx[0:15]";
	setAttr ".gtag[3].gtagnm" -type "string" "cylBottomRing";
	setAttr ".gtag[3].gtagcmp" -type "componentList" 1 "vtx[0:15]";
	setAttr ".gtag[4].gtagnm" -type "string" "cylSides";
	setAttr ".gtag[4].gtagcmp" -type "componentList" 1 "vtx[0:207]";
	setAttr ".gtag[5].gtagnm" -type "string" "cylTopCap";
	setAttr ".gtag[5].gtagcmp" -type "componentList" 1 "vtx[192:207]";
	setAttr ".gtag[6].gtagnm" -type "string" "cylTopRing";
	setAttr ".gtag[6].gtagcmp" -type "componentList" 1 "vtx[192:207]";
	setAttr ".gtag[7].gtagnm" -type "string" "sides";
	setAttr ".gtag[7].gtagcmp" -type "componentList" 1 "f[0:191]";
	setAttr ".gtag[8].gtagnm" -type "string" "top";
	setAttr ".gtag[8].gtagcmp" -type "componentList" 1 "f[193]";
	setAttr ".gtag[9].gtagnm" -type "string" "topRing";
	setAttr ".gtag[9].gtagcmp" -type "componentList" 1 "e[192:207]";
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 253 ".uvst[0].uvsp";
	setAttr ".uvst[0].uvsp[0:249]" -type "float2" 0.9638195 0.077164635 0.85543323
		 0.036611706 0.69322163 0.0095150918 0.50187993 0 0.31053817 0.0095150471 0.14832646
		 0.036611617 0.03994 0.077164531 0.0018796921 0.12499996 0.03993988 0.17283538 0.14832622
		 0.21338832 0.31053787 0.24048492 0.50187963 0.25 0.69322133 0.24048495 0.85543299
		 0.21338835 0.9638195 0.17283544 1.0018796921 0.125 0 0.25 0.0625 0.25 0.125 0.25
		 0.1875 0.25 0.25 0.25 0.3125 0.25 0.375 0.25 0.4375 0.25 0.5 0.25 0.5625 0.25 0.625
		 0.25 0.6875 0.25 0.75 0.25 0.8125 0.25 0.875 0.25 0.9375 0.25 1 0.25 0 0.29166666
		 0.0625 0.29166666 0.125 0.29166666 0.1875 0.29166666 0.25 0.29166666 0.3125 0.29166666
		 0.375 0.29166666 0.4375 0.29166666 0.5 0.29166666 0.5625 0.29166666 0.625 0.29166666
		 0.6875 0.29166666 0.75 0.29166666 0.8125 0.29166666 0.875 0.29166666 0.9375 0.29166666
		 1 0.29166666 0 0.33333331 0.0625 0.33333331 0.125 0.33333331 0.1875 0.33333331 0.25
		 0.33333331 0.3125 0.33333331 0.375 0.33333331 0.4375 0.33333331 0.5 0.33333331 0.5625
		 0.33333331 0.625 0.33333331 0.6875 0.33333331 0.75 0.33333331 0.8125 0.33333331 0.875
		 0.33333331 0.9375 0.33333331 1 0.33333331 0 0.37499997 0.0625 0.37499997 0.125 0.37499997
		 0.1875 0.37499997 0.25 0.37499997 0.3125 0.37499997 0.375 0.37499997 0.4375 0.37499997
		 0.5 0.37499997 0.5625 0.37499997 0.625 0.37499997 0.6875 0.37499997 0.75 0.37499997
		 0.8125 0.37499997 0.875 0.37499997 0.9375 0.37499997 1 0.37499997 0 0.41666663 0.0625
		 0.41666663 0.125 0.41666663 0.1875 0.41666663 0.25 0.41666663 0.3125 0.41666663 0.375
		 0.41666663 0.4375 0.41666663 0.5 0.41666663 0.5625 0.41666663 0.625 0.41666663 0.6875
		 0.41666663 0.75 0.41666663 0.8125 0.41666663 0.875 0.41666663 0.9375 0.41666663 1
		 0.41666663 0 0.45833328 0.0625 0.45833328 0.125 0.45833328 0.1875 0.45833328 0.25
		 0.45833328 0.3125 0.45833328 0.375 0.45833328 0.4375 0.45833328 0.5 0.45833328 0.5625
		 0.45833328 0.625 0.45833328 0.6875 0.45833328 0.75 0.45833328 0.8125 0.45833328 0.875
		 0.45833328 0.9375 0.45833328 1 0.45833328 0 0.49999994 0.0625 0.49999994 0.125 0.49999994
		 0.1875 0.49999994 0.25 0.49999994 0.3125 0.49999994 0.375 0.49999994 0.4375 0.49999994
		 0.5 0.49999994 0.5625 0.49999994 0.625 0.49999994 0.6875 0.49999994 0.75 0.49999994
		 0.8125 0.49999994 0.875 0.49999994 0.9375 0.49999994 1 0.49999994 0 0.54166663 0.0625
		 0.54166663 0.125 0.54166663 0.1875 0.54166663 0.25 0.54166663 0.3125 0.54166663 0.375
		 0.54166663 0.4375 0.54166663 0.5 0.54166663 0.5625 0.54166663 0.625 0.54166663 0.6875
		 0.54166663 0.75 0.54166663 0.8125 0.54166663 0.875 0.54166663 0.9375 0.54166663 1
		 0.54166663 0 0.58333331 0.0625 0.58333331 0.125 0.58333331 0.1875 0.58333331 0.25
		 0.58333331 0.3125 0.58333331 0.375 0.58333331 0.4375 0.58333331 0.5 0.58333331 0.5625
		 0.58333331 0.625 0.58333331 0.6875 0.58333331 0.75 0.58333331 0.8125 0.58333331 0.875
		 0.58333331 0.9375 0.58333331 1 0.58333331 0 0.625 0.0625 0.625 0.125 0.625 0.1875
		 0.625 0.25 0.625 0.3125 0.625 0.375 0.625 0.4375 0.625 0.5 0.625 0.5625 0.625 0.625
		 0.625 0.6875 0.625 0.75 0.625 0.8125 0.625 0.875 0.625 0.9375 0.625 1 0.625 0 0.66666669
		 0.0625 0.66666669 0.125 0.66666669 0.1875 0.66666669 0.25 0.66666669 0.3125 0.66666669
		 0.375 0.66666669 0.4375 0.66666669 0.5 0.66666669 0.5625 0.66666669 0.625 0.66666669
		 0.6875 0.66666669 0.75 0.66666669 0.8125 0.66666669 0.875 0.66666669 0.9375 0.66666669
		 1 0.66666669 0 0.70833337 0.0625 0.70833337 0.125 0.70833337 0.1875 0.70833337 0.25
		 0.70833337 0.3125 0.70833337 0.375 0.70833337 0.4375 0.70833337 0.5 0.70833337 0.5625
		 0.70833337 0.625 0.70833337 0.6875 0.70833337 0.75 0.70833337 0.8125 0.70833337 0.875
		 0.70833337 0.9375 0.70833337 1 0.70833337 0 0.75000006 0.0625 0.75000006 0.125 0.75000006
		 0.1875 0.75000006 0.25 0.75000006 0.3125 0.75000006 0.375 0.75000006 0.4375 0.75000006
		 0.5 0.75000006 0.5625 0.75000006 0.625 0.75000006 0.6875 0.75000006 0.75 0.75000006
		 0.8125 0.75000006 0.875 0.75000006 0.9375 0.75000006 1 0.75000006 0.9638195 0.82716465
		 0.85543323 0.78661168 0.69322163 0.75951511 0.50187993 0.75 0.31053817 0.75951505
		 0.14832646 0.78661162 0.03994 0.82716453 0.0018796921 0.87499994 0.03993988 0.92283535
		 0.14832622 0.96338832 0.31053787 0.99048495 0.50187963 1 0.69322133 0.99048495;
	setAttr ".uvst[0].uvsp[250:252]" 0.85543299 0.96338832 0.9638195 0.92283547
		 1.0018796921 0.875;
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr -s 208 ".vt";
	setAttr ".vt[0:165]"  0.92387974 -3 -0.38268289 0.70710713 -3 -0.70710635
		 0.3826839 -3 -0.92387927 5.0663948e-07 -3 -0.99999994 -0.38268298 -3 -0.92387968
		 -0.70710647 -3 -0.70710707 -0.92387938 -3 -0.38268378 -1 -3 -3.5762787e-07 -0.92387962 -3 0.38268313
		 -0.70710695 -3 0.70710659 -0.3826836 -3 0.92387944 -1.4901161e-07 -3 1 0.38268331 -3 0.92387956
		 0.70710671 -3 0.70710683 0.9238795 -3 0.38268346 1 -3 0 0.92387974 -2.5 -0.38268289
		 0.70710713 -2.5 -0.70710635 0.3826839 -2.5 -0.92387927 5.0663948e-07 -2.5 -0.99999994
		 -0.38268298 -2.5 -0.92387968 -0.70710647 -2.5 -0.70710707 -0.92387938 -2.5 -0.38268378
		 -1 -2.5 -3.5762787e-07 -0.92387962 -2.5 0.38268313 -0.70710695 -2.5 0.70710659 -0.3826836 -2.5 0.92387944
		 -1.4901161e-07 -2.5 1 0.38268331 -2.5 0.92387956 0.70710671 -2.5 0.70710683 0.9238795 -2.5 0.38268346
		 1 -2.5 0 0.92387974 -2 -0.38268289 0.70710713 -2 -0.70710635 0.3826839 -2 -0.92387927
		 5.0663948e-07 -2 -0.99999994 -0.38268298 -2 -0.92387968 -0.70710647 -2 -0.70710707
		 -0.92387938 -2 -0.38268378 -1 -2 -3.5762787e-07 -0.92387962 -2 0.38268313 -0.70710695 -2 0.70710659
		 -0.3826836 -2 0.92387944 -1.4901161e-07 -2 1 0.38268331 -2 0.92387956 0.70710671 -2 0.70710683
		 0.9238795 -2 0.38268346 1 -2 0 0.92387974 -1.5 -0.38268289 0.70710713 -1.5 -0.70710635
		 0.3826839 -1.5 -0.92387927 5.0663948e-07 -1.5 -0.99999994 -0.38268298 -1.5 -0.92387968
		 -0.70710647 -1.5 -0.70710707 -0.92387938 -1.5 -0.38268378 -1 -1.5 -3.5762787e-07
		 -0.92387962 -1.5 0.38268313 -0.70710695 -1.5 0.70710659 -0.3826836 -1.5 0.92387944
		 -1.4901161e-07 -1.5 1 0.38268331 -1.5 0.92387956 0.70710671 -1.5 0.70710683 0.9238795 -1.5 0.38268346
		 1 -1.5 0 0.92387974 -1 -0.38268289 0.70710713 -1 -0.70710635 0.3826839 -1 -0.92387927
		 5.0663948e-07 -1 -0.99999994 -0.38268298 -1 -0.92387968 -0.70710647 -1 -0.70710707
		 -0.92387938 -1 -0.38268378 -1 -1 -3.5762787e-07 -0.92387962 -1 0.38268313 -0.70710695 -1 0.70710659
		 -0.3826836 -1 0.92387944 -1.4901161e-07 -1 1 0.38268331 -1 0.92387956 0.70710671 -1 0.70710683
		 0.9238795 -1 0.38268346 1 -1 0 0.92387974 -0.5 -0.38268289 0.70710713 -0.5 -0.70710635
		 0.3826839 -0.5 -0.92387927 5.0663948e-07 -0.5 -0.99999994 -0.38268298 -0.5 -0.92387968
		 -0.70710647 -0.5 -0.70710707 -0.92387938 -0.5 -0.38268378 -1 -0.5 -3.5762787e-07
		 -0.92387962 -0.5 0.38268313 -0.70710695 -0.5 0.70710659 -0.3826836 -0.5 0.92387944
		 -1.4901161e-07 -0.5 1 0.38268331 -0.5 0.92387956 0.70710671 -0.5 0.70710683 0.9238795 -0.5 0.38268346
		 1 -0.5 0 0.92387974 0 -0.38268289 0.70710713 0 -0.70710635 0.3826839 0 -0.92387927
		 5.0663948e-07 0 -0.99999994 -0.38268298 0 -0.92387968 -0.70710647 0 -0.70710707 -0.92387938 0 -0.38268378
		 -1 0 -3.5762787e-07 -0.92387962 0 0.38268313 -0.70710695 0 0.70710659 -0.3826836 0 0.92387944
		 -1.4901161e-07 0 1 0.38268331 0 0.92387956 0.70710671 0 0.70710683 0.9238795 0 0.38268346
		 1 0 0 0.92387974 0.5 -0.38268289 0.70710713 0.5 -0.70710635 0.3826839 0.5 -0.92387927
		 5.0663948e-07 0.5 -0.99999994 -0.38268298 0.5 -0.92387968 -0.70710647 0.5 -0.70710707
		 -0.92387938 0.5 -0.38268378 -1 0.5 -3.5762787e-07 -0.92387962 0.5 0.38268313 -0.70710695 0.5 0.70710659
		 -0.3826836 0.5 0.92387944 -1.4901161e-07 0.5 1 0.38268331 0.5 0.92387956 0.70710671 0.5 0.70710683
		 0.9238795 0.5 0.38268346 1 0.5 0 0.92387974 1 -0.38268289 0.70710713 1 -0.70710635
		 0.3826839 1 -0.92387927 5.0663948e-07 1 -0.99999994 -0.38268298 1 -0.92387968 -0.70710647 1 -0.70710707
		 -0.92387938 1 -0.38268378 -1 1 -3.5762787e-07 -0.92387962 1 0.38268313 -0.70710695 1 0.70710659
		 -0.3826836 1 0.92387944 -1.4901161e-07 1 1 0.38268331 1 0.92387956 0.70710671 1 0.70710683
		 0.9238795 1 0.38268346 1 1 0 0.92387974 1.5 -0.38268289 0.70710713 1.5 -0.70710635
		 0.3826839 1.5 -0.92387927 5.0663948e-07 1.5 -0.99999994 -0.38268298 1.5 -0.92387968
		 -0.70710647 1.5 -0.70710707 -0.92387938 1.5 -0.38268378 -1 1.5 -3.5762787e-07 -0.92387962 1.5 0.38268313
		 -0.70710695 1.5 0.70710659 -0.3826836 1.5 0.92387944 -1.4901161e-07 1.5 1 0.38268331 1.5 0.92387956
		 0.70710671 1.5 0.70710683 0.9238795 1.5 0.38268346 1 1.5 0 0.92387974 2 -0.38268289
		 0.70710713 2 -0.70710635 0.3826839 2 -0.92387927 5.0663948e-07 2 -0.99999994 -0.38268298 2 -0.92387968
		 -0.70710647 2 -0.70710707;
	setAttr ".vt[166:207]" -0.92387938 2 -0.38268378 -1 2 -3.5762787e-07 -0.92387962 2 0.38268313
		 -0.70710695 2 0.70710659 -0.3826836 2 0.92387944 -1.4901161e-07 2 1 0.38268331 2 0.92387956
		 0.70710671 2 0.70710683 0.9238795 2 0.38268346 1 2 0 0.92387974 2.5 -0.38268289 0.70710713 2.5 -0.70710635
		 0.3826839 2.5 -0.92387927 5.0663948e-07 2.5 -0.99999994 -0.38268298 2.5 -0.92387968
		 -0.70710647 2.5 -0.70710707 -0.92387938 2.5 -0.38268378 -1 2.5 -3.5762787e-07 -0.92387962 2.5 0.38268313
		 -0.70710695 2.5 0.70710659 -0.3826836 2.5 0.92387944 -1.4901161e-07 2.5 1 0.38268331 2.5 0.92387956
		 0.70710671 2.5 0.70710683 0.9238795 2.5 0.38268346 1 2.5 0 0.92387974 3 -0.38268289
		 0.70710713 3 -0.70710635 0.3826839 3 -0.92387927 5.0663948e-07 3 -0.99999994 -0.38268298 3 -0.92387968
		 -0.70710647 3 -0.70710707 -0.92387938 3 -0.38268378 -1 3 -3.5762787e-07 -0.92387962 3 0.38268313
		 -0.70710695 3 0.70710659 -0.3826836 3 0.92387944 -1.4901161e-07 3 1 0.38268331 3 0.92387956
		 0.70710671 3 0.70710683 0.9238795 3 0.38268346 1 3 0;
	setAttr -s 400 ".ed";
	setAttr ".ed[0:165]"  0 1 0 1 2 0 2 3 0 3 4 0 4 5 0 5 6 0 6 7 0 7 8 0 8 9 0
		 9 10 0 10 11 0 11 12 0 12 13 0 13 14 0 14 15 0 15 0 0 16 17 1 17 18 1 18 19 1 19 20 1
		 20 21 1 21 22 1 22 23 1 23 24 1 24 25 1 25 26 1 26 27 1 27 28 1 28 29 1 29 30 1 30 31 1
		 31 16 1 32 33 1 33 34 1 34 35 1 35 36 1 36 37 1 37 38 1 38 39 1 39 40 1 40 41 1 41 42 1
		 42 43 1 43 44 1 44 45 1 45 46 1 46 47 1 47 32 1 48 49 1 49 50 1 50 51 1 51 52 1 52 53 1
		 53 54 1 54 55 1 55 56 1 56 57 1 57 58 1 58 59 1 59 60 1 60 61 1 61 62 1 62 63 1 63 48 1
		 64 65 1 65 66 1 66 67 1 67 68 1 68 69 1 69 70 1 70 71 1 71 72 1 72 73 1 73 74 1 74 75 1
		 75 76 1 76 77 1 77 78 1 78 79 1 79 64 1 80 81 1 81 82 1 82 83 1 83 84 1 84 85 1 85 86 1
		 86 87 1 87 88 1 88 89 1 89 90 1 90 91 1 91 92 1 92 93 1 93 94 1 94 95 1 95 80 1 96 97 1
		 97 98 1 98 99 1 99 100 1 100 101 1 101 102 1 102 103 1 103 104 1 104 105 1 105 106 1
		 106 107 1 107 108 1 108 109 1 109 110 1 110 111 1 111 96 1 112 113 1 113 114 1 114 115 1
		 115 116 1 116 117 1 117 118 1 118 119 1 119 120 1 120 121 1 121 122 1 122 123 1 123 124 1
		 124 125 1 125 126 1 126 127 1 127 112 1 128 129 1 129 130 1 130 131 1 131 132 1 132 133 1
		 133 134 1 134 135 1 135 136 1 136 137 1 137 138 1 138 139 1 139 140 1 140 141 1 141 142 1
		 142 143 1 143 128 1 144 145 1 145 146 1 146 147 1 147 148 1 148 149 1 149 150 1 150 151 1
		 151 152 1 152 153 1 153 154 1 154 155 1 155 156 1 156 157 1 157 158 1 158 159 1 159 144 1
		 160 161 1 161 162 1 162 163 1 163 164 1 164 165 1 165 166 1;
	setAttr ".ed[166:331]" 166 167 1 167 168 1 168 169 1 169 170 1 170 171 1 171 172 1
		 172 173 1 173 174 1 174 175 1 175 160 1 176 177 1 177 178 1 178 179 1 179 180 1 180 181 1
		 181 182 1 182 183 1 183 184 1 184 185 1 185 186 1 186 187 1 187 188 1 188 189 1 189 190 1
		 190 191 1 191 176 1 192 193 0 193 194 0 194 195 0 195 196 0 196 197 0 197 198 0 198 199 0
		 199 200 0 200 201 0 201 202 0 202 203 0 203 204 0 204 205 0 205 206 0 206 207 0 207 192 0
		 0 16 1 1 17 1 2 18 1 3 19 1 4 20 1 5 21 1 6 22 1 7 23 1 8 24 1 9 25 1 10 26 1 11 27 1
		 12 28 1 13 29 1 14 30 1 15 31 1 16 32 1 17 33 1 18 34 1 19 35 1 20 36 1 21 37 1 22 38 1
		 23 39 1 24 40 1 25 41 1 26 42 1 27 43 1 28 44 1 29 45 1 30 46 1 31 47 1 32 48 1 33 49 1
		 34 50 1 35 51 1 36 52 1 37 53 1 38 54 1 39 55 1 40 56 1 41 57 1 42 58 1 43 59 1 44 60 1
		 45 61 1 46 62 1 47 63 1 48 64 1 49 65 1 50 66 1 51 67 1 52 68 1 53 69 1 54 70 1 55 71 1
		 56 72 1 57 73 1 58 74 1 59 75 1 60 76 1 61 77 1 62 78 1 63 79 1 64 80 1 65 81 1 66 82 1
		 67 83 1 68 84 1 69 85 1 70 86 1 71 87 1 72 88 1 73 89 1 74 90 1 75 91 1 76 92 1 77 93 1
		 78 94 1 79 95 1 80 96 1 81 97 1 82 98 1 83 99 1 84 100 1 85 101 1 86 102 1 87 103 1
		 88 104 1 89 105 1 90 106 1 91 107 1 92 108 1 93 109 1 94 110 1 95 111 1 96 112 1
		 97 113 1 98 114 1 99 115 1 100 116 1 101 117 1 102 118 1 103 119 1 104 120 1 105 121 1
		 106 122 1 107 123 1 108 124 1 109 125 1 110 126 1 111 127 1 112 128 1 113 129 1 114 130 1
		 115 131 1 116 132 1 117 133 1 118 134 1 119 135 1 120 136 1 121 137 1 122 138 1 123 139 1;
	setAttr ".ed[332:399]" 124 140 1 125 141 1 126 142 1 127 143 1 128 144 1 129 145 1
		 130 146 1 131 147 1 132 148 1 133 149 1 134 150 1 135 151 1 136 152 1 137 153 1 138 154 1
		 139 155 1 140 156 1 141 157 1 142 158 1 143 159 1 144 160 1 145 161 1 146 162 1 147 163 1
		 148 164 1 149 165 1 150 166 1 151 167 1 152 168 1 153 169 1 154 170 1 155 171 1 156 172 1
		 157 173 1 158 174 1 159 175 1 160 176 1 161 177 1 162 178 1 163 179 1 164 180 1 165 181 1
		 166 182 1 167 183 1 168 184 1 169 185 1 170 186 1 171 187 1 172 188 1 173 189 1 174 190 1
		 175 191 1 176 192 1 177 193 1 178 194 1 179 195 1 180 196 1 181 197 1 182 198 1 183 199 1
		 184 200 1 185 201 1 186 202 1 187 203 1 188 204 1 189 205 1 190 206 1 191 207 1;
	setAttr -s 194 -ch 800 ".fc[0:193]" -type "polyFaces" 
		f 4 0 209 -17 -209
		mu 0 4 16 17 34 33
		f 4 1 210 -18 -210
		mu 0 4 17 18 35 34
		f 4 2 211 -19 -211
		mu 0 4 18 19 36 35
		f 4 3 212 -20 -212
		mu 0 4 19 20 37 36
		f 4 4 213 -21 -213
		mu 0 4 20 21 38 37
		f 4 5 214 -22 -214
		mu 0 4 21 22 39 38
		f 4 6 215 -23 -215
		mu 0 4 22 23 40 39
		f 4 7 216 -24 -216
		mu 0 4 23 24 41 40
		f 4 8 217 -25 -217
		mu 0 4 24 25 42 41
		f 4 9 218 -26 -218
		mu 0 4 25 26 43 42
		f 4 10 219 -27 -219
		mu 0 4 26 27 44 43
		f 4 11 220 -28 -220
		mu 0 4 27 28 45 44
		f 4 12 221 -29 -221
		mu 0 4 28 29 46 45
		f 4 13 222 -30 -222
		mu 0 4 29 30 47 46
		f 4 14 223 -31 -223
		mu 0 4 30 31 48 47
		f 4 15 208 -32 -224
		mu 0 4 31 32 49 48
		f 4 16 225 -33 -225
		mu 0 4 33 34 51 50
		f 4 17 226 -34 -226
		mu 0 4 34 35 52 51
		f 4 18 227 -35 -227
		mu 0 4 35 36 53 52
		f 4 19 228 -36 -228
		mu 0 4 36 37 54 53
		f 4 20 229 -37 -229
		mu 0 4 37 38 55 54
		f 4 21 230 -38 -230
		mu 0 4 38 39 56 55
		f 4 22 231 -39 -231
		mu 0 4 39 40 57 56
		f 4 23 232 -40 -232
		mu 0 4 40 41 58 57
		f 4 24 233 -41 -233
		mu 0 4 41 42 59 58
		f 4 25 234 -42 -234
		mu 0 4 42 43 60 59
		f 4 26 235 -43 -235
		mu 0 4 43 44 61 60
		f 4 27 236 -44 -236
		mu 0 4 44 45 62 61
		f 4 28 237 -45 -237
		mu 0 4 45 46 63 62
		f 4 29 238 -46 -238
		mu 0 4 46 47 64 63
		f 4 30 239 -47 -239
		mu 0 4 47 48 65 64
		f 4 31 224 -48 -240
		mu 0 4 48 49 66 65
		f 4 32 241 -49 -241
		mu 0 4 50 51 68 67
		f 4 33 242 -50 -242
		mu 0 4 51 52 69 68
		f 4 34 243 -51 -243
		mu 0 4 52 53 70 69
		f 4 35 244 -52 -244
		mu 0 4 53 54 71 70
		f 4 36 245 -53 -245
		mu 0 4 54 55 72 71
		f 4 37 246 -54 -246
		mu 0 4 55 56 73 72
		f 4 38 247 -55 -247
		mu 0 4 56 57 74 73
		f 4 39 248 -56 -248
		mu 0 4 57 58 75 74
		f 4 40 249 -57 -249
		mu 0 4 58 59 76 75
		f 4 41 250 -58 -250
		mu 0 4 59 60 77 76
		f 4 42 251 -59 -251
		mu 0 4 60 61 78 77
		f 4 43 252 -60 -252
		mu 0 4 61 62 79 78
		f 4 44 253 -61 -253
		mu 0 4 62 63 80 79
		f 4 45 254 -62 -254
		mu 0 4 63 64 81 80
		f 4 46 255 -63 -255
		mu 0 4 64 65 82 81
		f 4 47 240 -64 -256
		mu 0 4 65 66 83 82
		f 4 48 257 -65 -257
		mu 0 4 67 68 85 84
		f 4 49 258 -66 -258
		mu 0 4 68 69 86 85
		f 4 50 259 -67 -259
		mu 0 4 69 70 87 86
		f 4 51 260 -68 -260
		mu 0 4 70 71 88 87
		f 4 52 261 -69 -261
		mu 0 4 71 72 89 88
		f 4 53 262 -70 -262
		mu 0 4 72 73 90 89
		f 4 54 263 -71 -263
		mu 0 4 73 74 91 90
		f 4 55 264 -72 -264
		mu 0 4 74 75 92 91
		f 4 56 265 -73 -265
		mu 0 4 75 76 93 92
		f 4 57 266 -74 -266
		mu 0 4 76 77 94 93
		f 4 58 267 -75 -267
		mu 0 4 77 78 95 94
		f 4 59 268 -76 -268
		mu 0 4 78 79 96 95
		f 4 60 269 -77 -269
		mu 0 4 79 80 97 96
		f 4 61 270 -78 -270
		mu 0 4 80 81 98 97
		f 4 62 271 -79 -271
		mu 0 4 81 82 99 98
		f 4 63 256 -80 -272
		mu 0 4 82 83 100 99
		f 4 64 273 -81 -273
		mu 0 4 84 85 102 101
		f 4 65 274 -82 -274
		mu 0 4 85 86 103 102
		f 4 66 275 -83 -275
		mu 0 4 86 87 104 103
		f 4 67 276 -84 -276
		mu 0 4 87 88 105 104
		f 4 68 277 -85 -277
		mu 0 4 88 89 106 105
		f 4 69 278 -86 -278
		mu 0 4 89 90 107 106
		f 4 70 279 -87 -279
		mu 0 4 90 91 108 107
		f 4 71 280 -88 -280
		mu 0 4 91 92 109 108
		f 4 72 281 -89 -281
		mu 0 4 92 93 110 109
		f 4 73 282 -90 -282
		mu 0 4 93 94 111 110
		f 4 74 283 -91 -283
		mu 0 4 94 95 112 111
		f 4 75 284 -92 -284
		mu 0 4 95 96 113 112
		f 4 76 285 -93 -285
		mu 0 4 96 97 114 113
		f 4 77 286 -94 -286
		mu 0 4 97 98 115 114
		f 4 78 287 -95 -287
		mu 0 4 98 99 116 115
		f 4 79 272 -96 -288
		mu 0 4 99 100 117 116
		f 4 80 289 -97 -289
		mu 0 4 101 102 119 118
		f 4 81 290 -98 -290
		mu 0 4 102 103 120 119
		f 4 82 291 -99 -291
		mu 0 4 103 104 121 120
		f 4 83 292 -100 -292
		mu 0 4 104 105 122 121
		f 4 84 293 -101 -293
		mu 0 4 105 106 123 122
		f 4 85 294 -102 -294
		mu 0 4 106 107 124 123
		f 4 86 295 -103 -295
		mu 0 4 107 108 125 124
		f 4 87 296 -104 -296
		mu 0 4 108 109 126 125
		f 4 88 297 -105 -297
		mu 0 4 109 110 127 126
		f 4 89 298 -106 -298
		mu 0 4 110 111 128 127
		f 4 90 299 -107 -299
		mu 0 4 111 112 129 128
		f 4 91 300 -108 -300
		mu 0 4 112 113 130 129
		f 4 92 301 -109 -301
		mu 0 4 113 114 131 130
		f 4 93 302 -110 -302
		mu 0 4 114 115 132 131
		f 4 94 303 -111 -303
		mu 0 4 115 116 133 132
		f 4 95 288 -112 -304
		mu 0 4 116 117 134 133
		f 4 96 305 -113 -305
		mu 0 4 118 119 136 135
		f 4 97 306 -114 -306
		mu 0 4 119 120 137 136
		f 4 98 307 -115 -307
		mu 0 4 120 121 138 137
		f 4 99 308 -116 -308
		mu 0 4 121 122 139 138
		f 4 100 309 -117 -309
		mu 0 4 122 123 140 139
		f 4 101 310 -118 -310
		mu 0 4 123 124 141 140
		f 4 102 311 -119 -311
		mu 0 4 124 125 142 141
		f 4 103 312 -120 -312
		mu 0 4 125 126 143 142
		f 4 104 313 -121 -313
		mu 0 4 126 127 144 143
		f 4 105 314 -122 -314
		mu 0 4 127 128 145 144
		f 4 106 315 -123 -315
		mu 0 4 128 129 146 145
		f 4 107 316 -124 -316
		mu 0 4 129 130 147 146
		f 4 108 317 -125 -317
		mu 0 4 130 131 148 147
		f 4 109 318 -126 -318
		mu 0 4 131 132 149 148
		f 4 110 319 -127 -319
		mu 0 4 132 133 150 149
		f 4 111 304 -128 -320
		mu 0 4 133 134 151 150
		f 4 112 321 -129 -321
		mu 0 4 135 136 153 152
		f 4 113 322 -130 -322
		mu 0 4 136 137 154 153
		f 4 114 323 -131 -323
		mu 0 4 137 138 155 154
		f 4 115 324 -132 -324
		mu 0 4 138 139 156 155
		f 4 116 325 -133 -325
		mu 0 4 139 140 157 156
		f 4 117 326 -134 -326
		mu 0 4 140 141 158 157
		f 4 118 327 -135 -327
		mu 0 4 141 142 159 158
		f 4 119 328 -136 -328
		mu 0 4 142 143 160 159
		f 4 120 329 -137 -329
		mu 0 4 143 144 161 160
		f 4 121 330 -138 -330
		mu 0 4 144 145 162 161
		f 4 122 331 -139 -331
		mu 0 4 145 146 163 162
		f 4 123 332 -140 -332
		mu 0 4 146 147 164 163
		f 4 124 333 -141 -333
		mu 0 4 147 148 165 164
		f 4 125 334 -142 -334
		mu 0 4 148 149 166 165
		f 4 126 335 -143 -335
		mu 0 4 149 150 167 166
		f 4 127 320 -144 -336
		mu 0 4 150 151 168 167
		f 4 128 337 -145 -337
		mu 0 4 152 153 170 169
		f 4 129 338 -146 -338
		mu 0 4 153 154 171 170
		f 4 130 339 -147 -339
		mu 0 4 154 155 172 171
		f 4 131 340 -148 -340
		mu 0 4 155 156 173 172
		f 4 132 341 -149 -341
		mu 0 4 156 157 174 173
		f 4 133 342 -150 -342
		mu 0 4 157 158 175 174
		f 4 134 343 -151 -343
		mu 0 4 158 159 176 175
		f 4 135 344 -152 -344
		mu 0 4 159 160 177 176
		f 4 136 345 -153 -345
		mu 0 4 160 161 178 177
		f 4 137 346 -154 -346
		mu 0 4 161 162 179 178
		f 4 138 347 -155 -347
		mu 0 4 162 163 180 179
		f 4 139 348 -156 -348
		mu 0 4 163 164 181 180
		f 4 140 349 -157 -349
		mu 0 4 164 165 182 181
		f 4 141 350 -158 -350
		mu 0 4 165 166 183 182
		f 4 142 351 -159 -351
		mu 0 4 166 167 184 183
		f 4 143 336 -160 -352
		mu 0 4 167 168 185 184
		f 4 144 353 -161 -353
		mu 0 4 169 170 187 186
		f 4 145 354 -162 -354
		mu 0 4 170 171 188 187
		f 4 146 355 -163 -355
		mu 0 4 171 172 189 188
		f 4 147 356 -164 -356
		mu 0 4 172 173 190 189
		f 4 148 357 -165 -357
		mu 0 4 173 174 191 190
		f 4 149 358 -166 -358
		mu 0 4 174 175 192 191
		f 4 150 359 -167 -359
		mu 0 4 175 176 193 192
		f 4 151 360 -168 -360
		mu 0 4 176 177 194 193
		f 4 152 361 -169 -361
		mu 0 4 177 178 195 194
		f 4 153 362 -170 -362
		mu 0 4 178 179 196 195
		f 4 154 363 -171 -363
		mu 0 4 179 180 197 196
		f 4 155 364 -172 -364
		mu 0 4 180 181 198 197
		f 4 156 365 -173 -365
		mu 0 4 181 182 199 198
		f 4 157 366 -174 -366
		mu 0 4 182 183 200 199
		f 4 158 367 -175 -367
		mu 0 4 183 184 201 200
		f 4 159 352 -176 -368
		mu 0 4 184 185 202 201
		f 4 160 369 -177 -369
		mu 0 4 186 187 204 203
		f 4 161 370 -178 -370
		mu 0 4 187 188 205 204
		f 4 162 371 -179 -371
		mu 0 4 188 189 206 205
		f 4 163 372 -180 -372
		mu 0 4 189 190 207 206
		f 4 164 373 -181 -373
		mu 0 4 190 191 208 207
		f 4 165 374 -182 -374
		mu 0 4 191 192 209 208
		f 4 166 375 -183 -375
		mu 0 4 192 193 210 209
		f 4 167 376 -184 -376
		mu 0 4 193 194 211 210
		f 4 168 377 -185 -377
		mu 0 4 194 195 212 211
		f 4 169 378 -186 -378
		mu 0 4 195 196 213 212
		f 4 170 379 -187 -379
		mu 0 4 196 197 214 213
		f 4 171 380 -188 -380
		mu 0 4 197 198 215 214
		f 4 172 381 -189 -381
		mu 0 4 198 199 216 215
		f 4 173 382 -190 -382
		mu 0 4 199 200 217 216
		f 4 174 383 -191 -383
		mu 0 4 200 201 218 217
		f 4 175 368 -192 -384
		mu 0 4 201 202 219 218
		f 4 176 385 -193 -385
		mu 0 4 203 204 221 220
		f 4 177 386 -194 -386
		mu 0 4 204 205 222 221
		f 4 178 387 -195 -387
		mu 0 4 205 206 223 222
		f 4 179 388 -196 -388
		mu 0 4 206 207 224 223
		f 4 180 389 -197 -389
		mu 0 4 207 208 225 224
		f 4 181 390 -198 -390
		mu 0 4 208 209 226 225
		f 4 182 391 -199 -391
		mu 0 4 209 210 227 226
		f 4 183 392 -200 -392
		mu 0 4 210 211 228 227
		f 4 184 393 -201 -393
		mu 0 4 211 212 229 228
		f 4 185 394 -202 -394
		mu 0 4 212 213 230 229
		f 4 186 395 -203 -395
		mu 0 4 213 214 231 230
		f 4 187 396 -204 -396
		mu 0 4 214 215 232 231
		f 4 188 397 -205 -397
		mu 0 4 215 216 233 232
		f 4 189 398 -206 -398
		mu 0 4 216 217 234 233
		f 4 190 399 -207 -399
		mu 0 4 217 218 235 234
		f 4 191 384 -208 -400
		mu 0 4 218 219 236 235
		f 16 -16 -15 -14 -13 -12 -11 -10 -9 -8 -7 -6 -5 -4 -3 -2 -1
		mu 0 16 0 15 14 13 12 11 10 9 8 7 6 5 4 3 2 1
		f 16 192 193 194 195 196 197 198 199 200 201 202 203 204 205 206 207
		mu 0 16 251 250 249 248 247 246 245 244 243 242 241 240 239 238 237 252;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
	setAttr ".cvd" -type "dataPolyComponent" Index_Data Vertex 0 ;
	setAttr ".pd[0]" -type "dataPolyComponent" Index_Data UV 0 ;
	setAttr ".hfd" -type "dataPolyComponent" Index_Data Face 0 ;
	setAttr ".ndt" 0;
createNode transform -n "twist1Handle";
	rename -uid "B253FD21-304B-15D2-876C-6E869030A7D5";
	setAttr ".t" -type "double3" 0 0 2.9802322387695312e-08 ;
	setAttr ".s" -type "double3" 3 3 3 ;
	setAttr ".smd" 7;
createNode deformTwist -n "twist1HandleShape" -p "twist1Handle";
	rename -uid "71603D01-9748-8C44-E35F-9F84A73FCDF2";
	setAttr -k off ".v";
	setAttr ".dd" -type "doubleArray" 4 -1 1 0 0 ;
	setAttr ".hw" 1.1;
createNode transform -n "tagRiveted0";
	rename -uid "A22A9389-0D40-2621-BF77-CBB8E7494182";
createNode mesh -n "tagRiveted0Shape" -p "tagRiveted0";
	rename -uid "377185D5-E747-BAB3-39EB-CB889EA84CC7";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr ".ndt" 0;
createNode transform -n "tagRiveted1";
	rename -uid "A7AA676D-D44B-7BA3-6D20-DA965B93FBD8";
createNode mesh -n "tagRiveted1Shape" -p "tagRiveted1";
	rename -uid "A0139C9A-544A-C107-5151-16AC47858FB5";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr ".ndt" 0;
createNode transform -n "tagRiveted2";
	rename -uid "0C5D68FF-2C4D-456E-58DE-A180778F3275";
createNode mesh -n "tagRiveted2Shape" -p "tagRiveted2";
	rename -uid "8D46F32C-1F4B-3873-6B94-EB8D72B2376C";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr ".ndt" 0;
createNode transform -n "tagRiveted3";
	rename -uid "60B5F286-F749-11A2-7FF0-3A9CBBF1CD7A";
createNode mesh -n "tagRiveted3Shape" -p "tagRiveted3";
	rename -uid "86276078-854D-941E-2B19-238DE1B569DD";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr ".ndt" 0;
createNode lightLinker -s -n "lightLinker1";
	rename -uid "696F95A4-CA42-D2AD-B764-69809C0E1A60";
	setAttr -s 2 ".lnk";
	setAttr -s 2 ".slnk";
createNode shapeEditorManager -n "shapeEditorManager";
	rename -uid "7D5E7286-9240-FADA-B914-179D8DB3AB80";
createNode poseInterpolatorManager -n "poseInterpolatorManager";
	rename -uid "309E7ABD-5040-55E2-0D4B-95A33123B226";
createNode displayLayerManager -n "layerManager";
	rename -uid "C19CDEFF-9547-A54A-1608-20BAC84CF047";
createNode displayLayer -n "defaultLayer";
	rename -uid "25CABEC8-9A46-A4B1-9F21-C09B1D6B27DB";
	setAttr ".ufem" -type "stringArray" 0  ;
createNode renderLayerManager -n "renderLayerManager";
	rename -uid "ABEB94DD-464E-7B07-8AA8-E8862632BFAB";
createNode renderLayer -n "defaultRenderLayer";
	rename -uid "417EF91D-AC44-87EC-A9A2-C280530B6AD2";
	setAttr ".g" yes;
createNode polyCylinder -n "polyCylinder1";
	rename -uid "BFF1A139-FD40-1A1C-44E9-6A95E436C5F4";
	setAttr ".h" 6;
	setAttr ".sa" 16;
	setAttr ".sh" 12;
createNode nonLinear -n "twist1";
	rename -uid "1F7B694D-3547-1FF3-4793-4080D488315E";
	addAttr -is true -ci true -k true -sn "sa" -ln "startAngle" -smn -15 -smx 15 -at "doubleAngle";
	addAttr -is true -ci true -k true -sn "ea" -ln "endAngle" -smn -15 -smx 15 -at "doubleAngle";
	addAttr -is true -ci true -k true -sn "lb" -ln "lowBound" -dv -1 -max 0 -smn -10 
		-smx 0 -at "double";
	addAttr -is true -ci true -k true -sn "hb" -ln "highBound" -dv 1 -min 0 -smn 0 -smx 
		10 -at "double";
	setAttr -k on ".sa";
	setAttr -k on ".ea";
	setAttr -k on ".lb";
	setAttr -k on ".hb";
createNode animCurveTA -n "twist1_endAngle";
	rename -uid "F1816B9A-B542-D44A-DBE1-6DACF0A32F42";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  1 0 120 540;
createNode polyCube -n "polyCube1";
	rename -uid "0A6CC5B0-FA45-5B17-F803-BC95E5C6E2E4";
	setAttr ".w" 0.5;
	setAttr ".h" 0.5;
	setAttr ".d" 0.5;
createNode decomposeMatrix -n "tagRiveted0_decomp";
	rename -uid "138091D4-5741-68BE-C24E-A4A9B3DB8743";
createNode polyCube -n "polyCube2";
	rename -uid "B733B5F3-D94C-71EA-4D71-929EE8C98C4E";
	setAttr ".w" 0.5;
	setAttr ".h" 0.5;
	setAttr ".d" 0.5;
createNode decomposeMatrix -n "tagRiveted1_decomp";
	rename -uid "BB6EE71A-1F44-1A8F-29A2-2C8CEB16164E";
createNode polyCube -n "polyCube3";
	rename -uid "7E38F779-3E46-0F7B-81B6-75A801D555E1";
	setAttr ".w" 0.5;
	setAttr ".h" 0.5;
	setAttr ".d" 0.5;
createNode decomposeMatrix -n "tagRiveted2_decomp";
	rename -uid "969076BF-5045-BABD-E801-3898B82069CD";
createNode polyCube -n "polyCube4";
	rename -uid "1D0AA588-6346-EB45-1BB4-298569F857C3";
	setAttr ".w" 0.5;
	setAttr ".h" 0.5;
	setAttr ".d" 0.5;
createNode decomposeMatrix -n "tagRiveted3_decomp";
	rename -uid "B84CEB3F-6943-2A07-3499-ABA78F350B33";
createNode procrustesTags -n "procrustesTags";
	rename -uid "32D2058A-0746-D70A-8655-ADB5418C4403";
	setAttr -s 4 ".clusterTags";
	setAttr ".clusterTags[0]" -type "string" "ring0";
	setAttr ".clusterTags[1]" -type "string" "ring1";
	setAttr ".clusterTags[2]" -type "string" "ring2";
	setAttr ".clusterTags[3]" -type "string" "ring3";
	setAttr -s 4 ".bindMatrices";
	setAttr ".bindMatrices[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 2.5000001024454832 -1.75 -2.0489096641540527e-08 1;
	setAttr ".bindMatrices[1]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 2.5000001024454832 -0.5 -2.0489096641540527e-08 1;
	setAttr ".bindMatrices[2]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 2.5000001024454832 0.75 -2.0489096641540527e-08 1;
	setAttr ".bindMatrices[3]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 2.5000001024454832 2.25 -2.0489096641540527e-08 1;
	setAttr -s 4 ".outMatrix";
createNode script -n "uiConfigurationScriptNode";
	rename -uid "B0CD3123-D145-E317-295A-B5AA523D05B9";
	setAttr ".b" -type "string" "// Maya Mel UI Configuration File.\n// No UI generated in batch mode.\n";
	setAttr ".st" 3;
createNode script -n "sceneConfigurationScriptNode";
	rename -uid "A105FA6E-5D47-8FB3-F46E-4895EF4321A5";
	setAttr ".b" -type "string" "playbackOptions -min 1 -max 120 -ast 1 -aet 200 ";
	setAttr ".st" 6;
select -ne :time1;
	setAttr ".o" 1;
	setAttr ".unw" 1;
select -ne :hardwareRenderingGlobals;
	setAttr ".otfna" -type "stringArray" 22 "NURBS Curves" "NURBS Surfaces" "Polygons" "Subdiv Surface" "Particles" "Particle Instance" "Fluids" "Strokes" "Image Planes" "UI" "Lights" "Cameras" "Locators" "Joints" "IK Handles" "Deformers" "Motion Trails" "Components" "Hair Systems" "Follicles" "Misc. UI" "Ornaments"  ;
	setAttr ".otfva" -type "Int32Array" 22 0 1 1 1 1 1
		 1 1 1 0 0 0 0 0 0 0 0 0
		 0 0 0 0 ;
	setAttr ".fprt" yes;
	setAttr ".rtfm" 3;
select -ne :renderPartition;
	setAttr -s 2 ".st";
select -ne :renderGlobalsList1;
select -ne :defaultShaderList1;
	setAttr -s 6 ".s";
select -ne :postProcessList1;
	setAttr -s 2 ".p";
select -ne :defaultRenderingList1;
select -ne :standardSurface1;
	setAttr ".bc" -type "float3" 0.40000001 0.40000001 0.40000001 ;
	setAttr ".sr" 0.5;
select -ne :openPBR_shader1;
	setAttr ".bc" -type "float3" 0.40000001 0.40000001 0.40000001 ;
	setAttr ".sr" 0.5;
select -ne :initialShadingGroup;
	setAttr -s 6 ".dsm";
	setAttr ".ro" yes;
select -ne :initialParticleSE;
	setAttr ".ro" yes;
select -ne :defaultRenderGlobals;
	addAttr -ci true -h true -sn "dss" -ln "defaultSurfaceShader" -dt "string";
	setAttr ".dss" -type "string" "openPBR_shader1";
select -ne :defaultResolution;
	setAttr ".pa" 1;
select -ne :defaultColorMgtGlobals;
	setAttr ".cfe" yes;
	setAttr ".cfp" -type "string" "<MAYA_RESOURCES>/OCIO-configs/Maya2022-default/config.ocio";
	setAttr ".vtn" -type "string" "ACES 1.0 SDR-video (sRGB)";
	setAttr ".vn" -type "string" "ACES 1.0 SDR-video";
	setAttr ".dn" -type "string" "sRGB";
	setAttr ".wsn" -type "string" "ACEScg";
	setAttr ".otn" -type "string" "ACES 1.0 SDR-video (sRGB)";
	setAttr ".potn" -type "string" "ACES 1.0 SDR-video (sRGB)";
select -ne :hardwareRenderGlobals;
	setAttr ".ctrs" 256;
	setAttr ".btrs" 512;
connectAttr "twist1.og[0]" "twistTubeShape.i";
connectAttr "polyCylinder1.out" "twistTubeShapeOrig.i";
connectAttr "twist1.msg" "twist1Handle.sml";
connectAttr "twist1.sa" "twist1HandleShape.sa";
connectAttr "twist1.ea" "twist1HandleShape.ea";
connectAttr "twist1.lb" "twist1HandleShape.lb";
connectAttr "twist1.hb" "twist1HandleShape.hb";
connectAttr "tagRiveted0_decomp.ot" "tagRiveted0.t";
connectAttr "tagRiveted0_decomp.or" "tagRiveted0.r";
connectAttr "polyCube1.out" "tagRiveted0Shape.i";
connectAttr "tagRiveted1_decomp.ot" "tagRiveted1.t";
connectAttr "tagRiveted1_decomp.or" "tagRiveted1.r";
connectAttr "polyCube2.out" "tagRiveted1Shape.i";
connectAttr "tagRiveted2_decomp.ot" "tagRiveted2.t";
connectAttr "tagRiveted2_decomp.or" "tagRiveted2.r";
connectAttr "polyCube3.out" "tagRiveted2Shape.i";
connectAttr "tagRiveted3_decomp.ot" "tagRiveted3.t";
connectAttr "tagRiveted3_decomp.or" "tagRiveted3.r";
connectAttr "polyCube4.out" "tagRiveted3Shape.i";
relationship "link" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "link" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
connectAttr "layerManager.dli[0]" "defaultLayer.id";
connectAttr "renderLayerManager.rlmi[0]" "defaultRenderLayer.rlid";
connectAttr "twistTubeShapeOrig.w" "twist1.ip[0].ig";
connectAttr "twistTubeShapeOrig.o" "twist1.orggeom[0]";
connectAttr "twist1_endAngle.o" "twist1.ea";
connectAttr "twist1HandleShape.dd" "twist1.dd";
connectAttr "twist1Handle.wm" "twist1.ma";
connectAttr "procrustesTags.outMatrix[0]" "tagRiveted0_decomp.imat";
connectAttr "tagRiveted0.ro" "tagRiveted0_decomp.ro";
connectAttr "procrustesTags.outMatrix[1]" "tagRiveted1_decomp.imat";
connectAttr "tagRiveted1.ro" "tagRiveted1_decomp.ro";
connectAttr "procrustesTags.outMatrix[2]" "tagRiveted2_decomp.imat";
connectAttr "tagRiveted2.ro" "tagRiveted2_decomp.ro";
connectAttr "procrustesTags.outMatrix[3]" "tagRiveted3_decomp.imat";
connectAttr "tagRiveted3.ro" "tagRiveted3_decomp.ro";
connectAttr "twistTubeShape.w" "procrustesTags.mesh";
connectAttr "twistTube_restShape.w" "procrustesTags.meshOrig";
connectAttr "defaultRenderLayer.msg" ":defaultRenderingList1.r" -na;
connectAttr "twistTubeShape.iog" ":initialShadingGroup.dsm" -na;
connectAttr "twistTube_restShape.iog" ":initialShadingGroup.dsm" -na;
connectAttr "tagRiveted0Shape.iog" ":initialShadingGroup.dsm" -na;
connectAttr "tagRiveted1Shape.iog" ":initialShadingGroup.dsm" -na;
connectAttr "tagRiveted2Shape.iog" ":initialShadingGroup.dsm" -na;
connectAttr "tagRiveted3Shape.iog" ":initialShadingGroup.dsm" -na;
// End of MPyConstraint_Procrustes_Tags.ma
