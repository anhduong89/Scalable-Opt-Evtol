% % ------ optimization_1: Maximize revenue
revenue(D, X, W*S) :- flight(D, E, W, X), distance(E,S).
:~ revenue(D, X, V). [-V@3, D, X]