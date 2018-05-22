#!/bin/bash

./simdb.sh database cv new "Simulation Subject" IOS-ITER-baseline-scenario ITER_I-15.0_B-5.3_DT ITER-full-field-H
./simdb.sh database cv new "Simulation Type" "pulse analysis" simulation interpretation prediction "scenario design" "controller development"
./simdb.sh database cv new "Spatial coverage" core edge
./simdb.sh database cv new "Temporal coverage" "current ramp-up" "current ramp-down" "current flat top" "L-H transition" "H-L transition"
./simdb.sh database cv new "IDSs present" equilibrium core_profiles summary edge_profiles
./simdb.sh database cv new "Fuelling species" H He D D-T
./simdb.sh database cv new "code" LOCUST SOLPS EFIT++