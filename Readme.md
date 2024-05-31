# In Finite Craft

A tool that helps users optimize their Infinite Craft routes.

The algorithm used is a heavily optimized iterative deepening depth-first search.

Every time a new depth is completed, I will publish the recipes as a release.

## Usage

Requires python 3.11-3.12.

Install the required packages with:
```commandline
pip install -r requirements.txt
```

Then, you need to provide headers in `headers.json` for the Neal API.
This is not a tutorial on how to scrape the API.

To run the script to start searching low-depth elements, simply run:
```commandline
python main.py
```

`speedrun.py` can help you check your speedrun recipes for errors.
`optimize.py` can help you optimize your speedruns.
Use `-h` for help with any CLI arguments.

## Methodology

Since people are discussing the methodology behind the iddfs algorithm 
used in my code for finding minimal # of crafts, I will explain it here.

The algorithm is very close to optimal, but experimentally, the time and requests 
are still worse than exponential time. Therefore, it is not appropriate
for use in things like the @Infinite Helper Bot (by Mikarific), which requires
the alrogithm to continuously update as new data gets uploaded, or for finding
a lineage to very deep elements. For that purpose, look towards something
like A* (with a good heuristic, such as starting from the leaf node and using
min(depth(A), depth(B)), suggested by @BRH0208).

### Definitions

First, a craft / step is the act of combining 2 things together.
The source of a result can be denoted by a pair of numbers `(x, y)`, 
where `x<=y`. (You can combine an element with itself)

However, working with pairs of numbers is a pain, so instead of `(x, y)`, the
pair `(x, y)` will be denoted as `z = x + y * (y+1) / 2`, such that if `z1 > z2`, 
then `y1 > y2` or `y1 == y2 and x1 > x2`.

We can therefore denote a GameState `g` as a list of integers, where `g[i]` is the
source of the `i`th craft, as outlined above. The depth of a GameState is the
number of crafts beyond the initial k elements. The initial state is depth 0, 
and we don't need to keep track of the source for the initial elements.

We call two GameStates equivalent if the set of elements is the same, irrespective
of how they are generated. We call a GameState minimal if the last element can not
appear in any previous depth.

At each step, if you have n elements, there are `n+1 choose 2` possible crafts.
We denote the number of crafts as `limit(i)`, where `i` is the number of elements.

Also, remember that the GameState is a tree / DAG, while the recipes form some
kind of hypergraph.

### Algorithm

As an IDDFS, we iterate on the GameState tree at an increasing depth.

At each depth, we generate all possible crafts, and then we check if the result
is a new possible element.

### Ordering of Elements

First of all, suppose we have a GameState `g`, of depth n.
If `g[i] > g[n]` and `i < n`, then `g[n] < limit(i)`, which means that we can
place `g[n]` at the i-th position in the GameState, and push everything else
backwards (obviously changing the source of the crafts respectively). The resulting
GameState is equivalent to the original GameState.

This means that for any GameState, we can sort the crafts such that `g[i] < g[j]`
for all `i < j`.

Order(GameState i) < Order(GameState j) if and only if 
`i[x] = j[x]` for x<k and `i[x] < j[x]` for x=k.

### Deduplication

The obvious part of deduplication is such that if at step `i`, we can craft element
`A` from two different sources, then we can ignore one of the sources. This is
easily achieved through the use of a set at each step.

However, we can push this condition further.

If we can get `(GameState 1) i1 -> i2 -> ... -> i(n-1) -> E` at depth n, 
and we can also get `(GameState 2) i1 -> i2 -> ... -> i(n-1) -> j1 -> j2 -> ... -> jm -> E` at depth n+m, where `(x + j_k) -> E` (E uses at least one of the new items):
- `Order(GameState 1) < Order(GameState 2)` --> there exists a recipe
`i1 -> i2 -> ... -> i(n-1) -> E -> j1 -> j2 -> ... -> jm`, 
so we don't need Recipe 2.

- `Order(GameState 2) < Order(GameState 1)` --> 
Both recipe 1 and 2 stays. 
Recipe 1 is more restrictive due to ordering 
(E or later elements must be used for any next crafts), while 
Recipe 2 crafted stuff before E, which may provide more options. 

This means that we should also keep track of what can be crafted in lower
order recipes at each step. Essentially, if we can craft `E` using elements
that only occur at a lower depth, then we can ignore the resulting GameState.

One example, by `analog_hors` on a discussion in Manechat, is:
```
Water + Fire -> Steam
Wind + Water -> Wave
Wave + Steam -> Surf
vs
Water + Wind -> Wave
Wave + Fire -> Steam
Steam + Wave -> Surf
```
If Wind > Fire in the starting order of elements, 
then the optimization above means that Wave + Fire = Steam 
will count as a collision. Specifically, we have
`n=1`, `m=1`, `E = Steam`, `j1 = Wave`,
and case `Order(Recipe 1) < Order(Recipe 2)`.

If Wind < Fire in the starting order of elements, 
then `Wind + Water -> Wave` in recipe 1 shouldn't exist 
because it's smaller in order but crafted later, violating the Ordering condition.

This is a bit stronger than the previous statement since it covers
recipes that wouldn't be checked due to Ordering restrictions, but its power
grows further if we include the next optimization as well.

### Using All Crafts

Why would you ever craft something if it isn't used? Maybe it will be used
later down the line, but we would never do such a thing in an optimal recipe.
If `g` is the optimal route for `B`, but element `A` is unused, 
then removing `A` would result in a lower depth and valid route for `B`,
which contradicts the optimality of `g`.

This means that we can keep track of which elements are unused during the
crafting process, and once there are simply too many to use within the
remaining depth, terminate the search.

### Why you can't optimize much further

After all of these optimizations, experimentally, every single GameState
corresponding with an optimal recipe is distinct. If you can prove that this is false and there's a bit of optimization to squeeze
out of the algorithm, please let me know. (Discord: stargazinghomies)

In the `1450602`* leaf nodes searched for depth 1~9 with this algorithm, there
are `47251`* recipes that are optimal and distinct (in all_best_recipes_depth_9.txt).
Given that we do not know what each combination will result in before requesting
the result from Neal's API, we don't know how deep the resulting element 
is through other paths, so `3.26%` seems reasonable.

However, the remaining leaf nodes likely correspond to a craft where after
we combine the last two elements, we see that it's actually better through
a completely different route. Expanding to all routes 1 off optimal grows the 
recipe list to `~150K`*, which is `~10%`. 

Even if we can get some optimal route, the amount of optimal elements also seems
to grow worse than exponentially, so there is eventually a limit.

*These numbers change due to a different dataset depending on when you are
reading this, and due to the occasional unreliability of `Nothing` responses from
Neal's API. However, the approximate percentage is the same.
