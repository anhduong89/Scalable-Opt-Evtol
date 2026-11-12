% ------ optimization_3: penalize empty flights.

penalty(D, E, S, 1) :- flight(D, E, 0, S).
:~ penalty(D, _, S, P). [P@1, D, S]
% % ------ optimization_2.1: penalize empty flights and not stationed. (could has better solution)

% penalty(D, E, S, 1) :- flight(D, E, 0, S), not edge_loop(E).
% :~ penalty(D, _, S, P). [P@0, D, S]