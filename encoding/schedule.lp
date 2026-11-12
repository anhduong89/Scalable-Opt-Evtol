% #include "T_ITS2025/instances/network_NY_0.lp".
% #include "T_ITS2025/instances/init.lp".
% #include "T_ITS2025/instances/rq.lp".
% #include "T_ITS2025/optional/h2.lp".
% #include "T_ITS2025/optional/o1.lp".
% #const start_seg = 1.
% #const max_seg = 11.
% #const horizon = 180.
% ------ INSTANCES
max_seg(D,max_seg):-agent(D).
% seg(1..max_seg).
% ------ GENERATE ROUTING

% -- assign edge to each segment
1 {flight(D,E,0..C,X):edge(E)} 1 :- agent(D), capacity(D,C), X=start_seg..max_seg.

% total delivered customers can not excess demand
:- (R+1) #sum{W,D,X:flight(D,E,W,X)}, edge(E), request(_,E,R).

:- 1 #sum{W,D,X:flight(D,E,W,X)}, edge(E), not request(_,E,_).

% stationed aircraft does not carry customers
:- flight(_,E,W,_), W > 0, edge_loop(E).

% start vertiport as specicfied
:- init_loc(D,V), flight(D,(V',_),_,1), V!=V'.

% consecutive trips need to be connected
:-flight(D,(V,V1),_,X),flight(D,(V2,V3),_,X+1),V1!=V2.

%  ----------------------------
% ----- TIME SCHEDULE WITH DIFFERENT CONSTRAINT
% start time at initial vertiport = charge duration

&diff {start(D,E,1)} = 0 :- flight(D,E,_,1).

&diff {arrival(D,E,M)} <= horizon :- flight(D,E,_,M).

&diff {arrival(D,E,X) - start(D,E,X)} = FT :- flight_time(E,FT), flight(D,E,_,X).

&diff {start(D,E',X+1) - arrival(D,E,X)} >= CT :- charge_time(E',CT), flight(D,E,_,X), flight(D,E',_,X+1).
%  ----------------------------

% display
#show flight/4.