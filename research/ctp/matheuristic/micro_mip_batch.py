"""Micro-MIP: Local Window Elementary Path Re-optimizer with Coverage Constraints.

Formulates and solves a localized elementary shortest path problem with coverage
constraints using SCIP with Miller-Tucker-Zemlin (MTZ) subtour elimination.
Freezes the outer tour and optimizes only the local window in milliseconds.
"""
import time
from pyscipopt import Model, quicksum
from instances import audit_route as _audit_route

def audit_route(d, route):
    return _audit_route(d, route, min_visits=2)


def reoptimize_window(d, route, start_idx, window_size, max_candidates=16, time_limit=1.0):
    """
    Re-optimize a window of `window_size` consecutive vertices in `route` starting at `start_idx`.

    Returns dict with:
        improved: bool
        old_cost: int (if improved)
        new_cost: int (if improved)
        gain: int (if improved)
        new_route: list[int] (if improved)
        time: float
    """
    k = len(route)
    if k < window_size + 2:
        return {'improved': False, 'reason': 'route_too_short'}

    anchor_a_idx = (start_idx - 1) % k
    anchor_b_idx = (start_idx + window_size) % k
    A = route[anchor_a_idx]
    B = route[anchor_b_idx]

    window_indices = [(start_idx + t) % k for t in range(window_size)]
    current_window_nodes = [route[i] for i in window_indices]

    # Frozen segment from B around to A
    frozen_indices = []
    curr = anchor_b_idx
    while curr != anchor_a_idx:
        frozen_indices.append(curr)
        curr = (curr + 1) % k
    frozen_indices.append(anchor_a_idx)
    frozen_nodes = [route[i] for i in frozen_indices]
    frozen_set = set(frozen_nodes)

    # Demands covered by the frozen path
    covered_frozen = set()
    for u in frozen_set:
        mask = d.masks[u]
        w = 0
        while (1 << w) <= mask:
            if mask & (1 << w):
                covered_frozen.add(w)
            w += 1

    uncovered_demands = [w for w in range(d.demands) if w not in covered_frozen]
    mandatory_unvisited = [u for u in d.mandatory if u not in frozen_set]

    # Candidate selection
    cand_set = set(current_window_nodes)
    cand_set.update(mandatory_unvisited)
    available = [u for u in range(d.n) if u not in frozen_set and u not in cand_set]

    def score_node(u):
        covers_count = sum(1 for w in uncovered_demands if d.masks[u] & (1 << w))
        dist = min(d.costs[A, u], d.costs[u, B]) + 1
        return covers_count / dist

    available.sort(key=score_node, reverse=True)
    for u in available:
        if len(cand_set) >= max_candidates:
            break
        cand_set.add(u)

    cand_list = sorted(list(cand_set))
    all_nodes = [A] + cand_list + [B]

    curr_path = [A] + current_window_nodes + [B]
    current_window_cost = sum(d.costs[curr_path[t], curr_path[t + 1]] for t in range(len(curr_path) - 1))

    t0 = time.perf_counter()
    m = Model('MicroMIP_Window')
    m.hideOutput()
    m.setRealParam('limits/time', time_limit)
    m.setIntParam('parallel/maxnthreads', 1)
    m.setRealParam('limits/gap', 0)

    y = {i: m.addVar(vtype='B', lb=1 if i in mandatory_unvisited else 0, name=f'y_{i}') for i in cand_list}

    x = {}
    for i in all_nodes:
        for j in all_nodes:
            if i != j and i != B and j != A:
                if i == A and j == B and uncovered_demands:
                    continue
                x[i, j] = m.addVar(vtype='B', obj=int(d.costs[i, j]), name=f'x_{i}_{j}')

    # Flow conservation at endpoints
    m.addCons(quicksum(x[A, j] for j in all_nodes if (A, j) in x) == 1)
    m.addCons(quicksum(x[i, B] for i in all_nodes if (i, B) in x) == 1)

    # Flow conservation at intermediate candidates
    for i in cand_list:
        m.addCons(quicksum(x[i, j] for j in all_nodes if (i, j) in x) == y[i])
        m.addCons(quicksum(x[j, i] for j in all_nodes if (j, i) in x) == y[i])

    # MTZ subtour elimination
    u_var = {i: m.addVar(vtype='C', lb=1, ub=len(cand_list), name=f'u_{i}') for i in cand_list}
    M = len(cand_list) + 1
    for i in cand_list:
        for j in cand_list:
            if (i, j) in x:
                m.addCons(u_var[i] - u_var[j] + M * x[i, j] <= M - 1)

    # Coverage of uncovered demands
    for w in uncovered_demands:
        covering_cands = [i for i in cand_list if d.masks[i] & (1 << w)]
        if not covering_cands:
            return {'improved': False, 'reason': 'uncoverable_in_window'}
        m.addCons(quicksum(y[i] for i in covering_cands) >= 1)

    # Warm start with current incumbent window
    s = m.createSol()
    for t in range(len(curr_path) - 1):
        edge = (curr_path[t], curr_path[t + 1])
        if edge in x:
            m.setSolVal(s, x[edge], 1)
    for node in current_window_nodes:
        if node in y:
            m.setSolVal(s, y[node], 1)
    for node in cand_list:
        order = current_window_nodes.index(node) + 1 if node in current_window_nodes else 1
        m.setSolVal(s, u_var[node], order)
    assert m.addSol(s), "Incumbent window warm start rejected"

    m.optimize()
    t1 = time.perf_counter()

    sol = m.getBestSol()
    if sol is None:
        return {'improved': False, 'time': t1 - t0}

    new_window_cost = round(m.getObjVal())

    if new_window_cost < current_window_cost:
        new_path = [A]
        curr = A
        visited_in_path = set([A])
        while curr != B:
            nxt = None
            for j in all_nodes:
                if (curr, j) in x and m.getSolVal(sol, x[curr, j]) > 0.5:
                    nxt = j
                    break
            assert nxt is not None, f"Path disconnected at {curr}"
            assert nxt not in visited_in_path, "Cycle in reconstructed path"
            new_path.append(nxt)
            curr = nxt
            visited_in_path.add(curr)
            if len(visited_in_path) > len(all_nodes):
                raise RuntimeError("Cycle detected in path reconstruction")

        new_window_nodes = new_path[1:-1]

        if anchor_a_idx < anchor_b_idx:
            new_route = route[:anchor_a_idx + 1] + new_window_nodes + route[anchor_b_idx:]
        else:
            new_route = new_window_nodes + route[anchor_b_idx:anchor_a_idx + 1]

        if 0 in new_route:
            idx0 = new_route.index(0)
            new_route = new_route[idx0:] + new_route[:idx0]

        audited_cost = audit_route(d, new_route)
        old_cost = audit_route(d, route)
        assert old_cost - audited_cost == current_window_cost - new_window_cost
        assert audited_cost < old_cost
        return {
            'improved': True,
            'old_cost': old_cost,
            'new_cost': audited_cost,
            'gain': old_cost - audited_cost,
            'time': t1 - t0,
            'new_route': new_route,
            'candidates': len(cand_list),
            'uncovered_demands': len(uncovered_demands)
        }

    return {
        'improved': False,
        'time': t1 - t0,
        'candidates': len(cand_list),
        'uncovered_demands': len(uncovered_demands)
    }


def polish_route(d, initial_route, window_sizes=(4, 6), max_candidates=16, max_passes=3):
    """
    Applies sliding window Micro-MIP passes over the route until no improving window is found.
    """
    current_route = list(initial_route)
    total_gain = 0
    t_start = time.perf_counter()
    passes = 0
    improved_any = True
    improvements_log = []

    while improved_any and passes < max_passes:
        improved_any = False
        passes += 1
        for w_size in window_sizes:
            k = len(current_route)
            if k < w_size + 3:
                continue
            for start in range(k):
                res = reoptimize_window(d, current_route, start, w_size,
                                         max_candidates=max_candidates, time_limit=1.0)
                if res.get('improved'):
                    gain = res['gain']
                    total_gain += gain
                    current_route = res['new_route']
                    improved_any = True
                    improvements_log.append({
                        'pass': passes,
                        'window_size': w_size,
                        'start_idx': start,
                        'gain': gain,
                        'cost': res['new_cost'],
                        'time': res['time']
                    })
                    break  # Restart scan with updated route

    elapsed = time.perf_counter() - t_start
    final_cost = audit_route(d, current_route)
    return {
        'initial_cost': audit_route(d, initial_route),
        'final_cost': final_cost,
        'total_gain': total_gain,
        'elapsed_seconds': elapsed,
        'passes': passes,
        'improvements_count': len(improvements_log),
        'improvements_log': improvements_log,
        'final_route': current_route
    }
