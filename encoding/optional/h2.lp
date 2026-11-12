% Prioritize scheduling higher-revenue flights earlier in the trajectory
#heuristic flight(_,E,W,X):distance(E,S). [W*S*(max_seg-X+1),true]