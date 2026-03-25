#heuristic as(_,E,W,X):distance(E,S). [W*S*(max_seg-X+1)@1,true]

#heuristic as(D,E,W,X):as(D,E,_,Y),distance(E,S). [W*S@2,true]