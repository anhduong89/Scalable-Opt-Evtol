% #include "T_ITS2025/instances/network_NY_0.lp".
% #include "T_ITS2025/instances/init.lp".
% #include "T_ITS2025/instances/rq.lp".
% #const max_seg=10.
% #const horizon=180.
% current_agent(0).
% seg(1).
max_seg(D,max_seg) :- agent(D).
% assign the highest revenue flights to the agent at current segment
1{as(D,E,0..C,X):edge(E)}1:- current_agent(D), seg(X), capacity(D,C).

% total delivered customers can not excess demand
:- (R+1) #sum{W,D,X:as(D,E,W,X)}, edge(E), request(_,E,R).

:- 1 #sum{W,D,X:as(D,E,W,X)}, edge(E), not request(_,E,_).

% stationed aircraft does not carry customers
:- as(_,E,W,_), W > 0, edge_loop(E).

% start vertiport as specicfied
:- init_loc(D,V), as(D,(V',_),_,1), V!=V'.

% consecutive trips need to be connected
:-as(D,(V,V1),_,X),as(D,(V2,V3),_,X+1),V1!=V2.
%  ----------------------------
% ----- TIME SCHEDULE WITH DIFFERENT CONSTRAINT
% start time at initial vertiport = charge duration

&diff {start(D,E,1)} = 0 :- as(D,E,_,1).

&diff {arrival(D,E,M)} <= horizon :- as(D,E,_,M), max_seg(D,M).

&diff {arrival(D,E,X) - start(D,E,X)} = FT :- flight_time(E,FT), as(D,E,_,X).

&diff {start(D,E',X+1) - arrival(D,E,X)} >= CT :- charge_time(E',CT), as(D,E,_,X), as(D,E',_,X+1).

#external current_agent(D) : agent(D).
%  ----------------------------

#heuristic as(_,E,W,X):distance(E,S). [W*S,true]
% display
#show as/4.