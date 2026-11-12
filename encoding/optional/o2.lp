% ------ optimization_2: penalize unserved customers.

% remain_cust(E,N-P) :- request(_,E,N), P=#sum{W,D,X: flight(D,E,W,X)}, N!=P.
% :~ remain_cust(E,P). [P@1, E]

% optimization_2, aggregate-free: maximize served passengers (= minimize unserved)
:~ flight(D,E,W,X). [-W@1, D,E,X]