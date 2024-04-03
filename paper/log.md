## The problem definition
There are $N$ parties each holding a set of elements. These parties want to know which elements appear in at least $t$ sets, for a certain threshold $t$, without revealing any information about elements that do not meet this threshold

## Parties
Participants $(P_i$): these hold the sets and they share a secret key $K$

Aggregator $(A)$: A single entity responsible for aggregating the inputs from participants and calculating the output.

## Definition of the function to be computed in semi-honest model

$S: \\{\ell : \forall \ell \in S\\}$ Domain of the set elements

$f: ((S_p: S_p \subseteq S)^N, \\{\\}) \mapsto (S_p: S_p \subseteq S)^{N+1}$ 

Input for each $P_i$: the set that participant holds, $S_i$  
Input of the $A$: empty set

Output for everyone: All $\ell$ for which there exist an $I$ such that:
$$I = \\{i : 0\leq i < N, i \in \mathbb{Z}\\}$$
$$|I| \geq t$$
$$\ell \in \bigcap_{i \in I} S_i \ $$

## Protocol
### Parameters:
$b$: bin size  
$t$: threshold

### Steps:
1. All $P_i$ decides on a symetric secret key $K$, without involving $A$
2. $A$ broadcasts a random number $r$ for this round
3. All $P_i$ runs the $CreateShareTree$ Algorithm and they send the result to $A$
4. $A$ runs the $SolveTree$ Algorithm and broadcasts the result

```
Poly(secret, shared_secret, degree, x):
    return secret + H(secret, shared_secret)x +
           H(H(secret, shared_secret))x^2 + ... +H(H(...))x^degree

CreateShareTree(S_p, K, r, i):
    let poly(secret) = Poly(secret, K, t, i)
    let a(x,y) = H(x,y,K,r)
    let shares = []
    let current_level = [(0, s) for s in S_p]
    for x=0 to log_t(|S|):
        let parents = []
        for element in current_level:
            parent = (x+1, element//b)
            share = ( H(i, a(parent)), poly(a(element)) )
            shares.append(share)
            parents.append(parent)
        current_level = parents
    root = (log_t(|S|), 0)
    return shares, root

SolveTree(Shares, root):
    possible_paths = [root]
    for x=0 to log_t(|S|):
        let new_possible_paths = []
        for parent in possible_paths:
            let children = []
            for n=0 to N:
                for share in Shares[n]:
                    if share[0] == H(n, parent):
                        children.append(share)
            
            for every (c1, c2, ... ct) combination of children:
                result = solvePoly(c1, c2, ... ct)
                if result is valid:
                    new_possible_paths.append(result)
        possible_paths = new_possible_paths
    
    return possible_paths
```
