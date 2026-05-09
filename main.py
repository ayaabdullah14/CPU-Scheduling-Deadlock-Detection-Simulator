import re
from collections import deque
from enum import Enum

NUM_PROCESSES = 3
NUM_RESOURCES = 3


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class StepType(Enum):
    CPU      = 'CPU'
    REQUEST  = 'R'
    RELEASE  = 'F'
    IO       = 'IO'


class Step:
    """
    A single atomic step inside a burst sequence.
      CPU     -> duration (int)
      REQUEST -> resource index (int)
      RELEASE -> resource index (int)
      IO      -> duration (int)
    """
    def __init__(self, step_type: StepType, value: int):
        self.step_type = step_type
        self.value     = value          # duration for CPU/IO, resource id for R/F
        self.remaining = value          # counts down for CPU/IO steps

    def __repr__(self):
        return f"{self.step_type.value}({self.value})"


class Process:
    def __init__(self, pid, arrival_time=0, priority=0):
        self.pid          = pid
        self.arrival_time = arrival_time
        self.priority     = priority
        self.steps        = []          # flat list of Step objects in order
        self.step_index   = 0          # next step to execute
        self.finished     = False

    def current_step(self):
        if self.step_index < len(self.steps):
            return self.steps[self.step_index]
        return None

    def advance_step(self):
        self.step_index += 1

    def __repr__(self):
        return (f"Process(pid={self.pid}, arrival={self.arrival_time}, "
                f"priority={self.priority}, steps={self.steps})")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_input_file(filename):
    processes = []
    with open(filename, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = re.split(r'\s+', line)
            if len(parts) < 4:
                continue
            try:
                pid          = int(parts[0])
                arrival_time = int(parts[1])
                priority     = int(parts[2])
                burst_str    = " ".join(parts[3:])
            except ValueError:
                continue
            p = Process(pid, arrival_time, priority)
            p.steps = parse_steps(burst_str)
            processes.append(p)
    return processes


def parse_steps(burst_str):
    """
    Convert a burst string like  CPU{R[1],15,R[2],10,F[1],F[2]}  IO{4}
    into an ordered flat list of Step objects.

    CPU{...} items are parsed in their written order so that
    R[x] -> int -> F[x] sequences execute correctly.
    """
    steps = []
    # Match top-level burst tokens
    token_pat = re.compile(r"(CPU\{[^}]+\}|IO\{[^}]+\})")
    for token in token_pat.finditer(burst_str):
        tok = token.group(1)
        if tok.startswith("CPU"):
            inner = re.search(r"CPU\{([^}]+)\}", tok).group(1)
            for item in [x.strip() for x in inner.split(',') if x.strip()]:
                if item.startswith('R['):
                    rid = int(re.search(r'\d+', item).group())
                    steps.append(Step(StepType.REQUEST, rid))
                elif item.startswith('F['):
                    rid = int(re.search(r'\d+', item).group())
                    steps.append(Step(StepType.RELEASE, rid))
                else:
                    try:
                        steps.append(Step(StepType.CPU, int(item)))
                    except ValueError:
                        pass
        elif tok.startswith("IO"):
            inner = re.search(r"IO\{([^}]+)\}", tok).group(1)
            for item in [x.strip() for x in inner.split(',') if x.strip()]:
                try:
                    steps.append(Step(StepType.IO, int(item)))
                except ValueError:
                    pass
    return steps


# ---------------------------------------------------------------------------
# Resource management
# ---------------------------------------------------------------------------

def allocate(process_index, resource_id, allocation, available):
    """Give one unit of resource_id to process_index."""
    allocation[process_index][resource_id] += 1
    available[resource_id]                 -= 1


def release(process_index, resource_id, allocation, available):
    """Take back one unit of resource_id from process_index."""
    if allocation[process_index][resource_id] > 0:
        allocation[process_index][resource_id] -= 1
        available[resource_id]                 += 1


def release_all(process_index, allocation, available):
    """Release every resource held by process_index."""
    for r in range(NUM_RESOURCES):
        if allocation[process_index][r] > 0:
            available[r]                 += allocation[process_index][r]
            allocation[process_index][r]  = 0


# ---------------------------------------------------------------------------
# Deadlock detection  (Banker's-style safety algorithm)
# ---------------------------------------------------------------------------

def detect_deadlock(allocation, need, available, active_set):
    """
    Returns list of process indices that are deadlocked.
    Only considers processes in active_set.
    need[i][r]  = resources still needed (requested but not yet granted)
    allocation[i][r] = resources currently held
    available[r]     = free resources
    """
    work   = available[:]
    finish = {i: False for i in active_set}

    changed = True
    while changed:
        changed = False
        for i in active_set:
            if finish[i]:
                continue
            if all(need[i][r] <= work[r] for r in range(NUM_RESOURCES)):
                for r in range(NUM_RESOURCES):
                    work[r] += allocation[i][r]
                finish[i] = True
                changed   = True

    return [i for i in active_set if not finish[i]]


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def round_robin_priority(processes, quantum):
    # Sort by arrival time for consistent initial ordering
    processes.sort(key=lambda x: x.arrival_time)
    n = len(processes)

    current_time      = 0
    ready_queue       = deque()     # indices of processes ready to run
    io_queue          = []          # (process_index, io_finish_time)
    waiting_queue     = {}          # process_index -> resource_id it is blocked on
    gantt_chart       = []
    completed         = set()

    # Per-process metrics
    last_ready_time   = [p.arrival_time for p in processes]   # when it last entered ready queue
    waiting_time      = [0] * n
    turnaround_time   = [0] * n
    finish_time       = [0] * n

    # Resource state
    allocation = [[0] * NUM_RESOURCES for _ in range(n)]
    need       = [[0] * NUM_RESOURCES for _ in range(n)]   # pending requests
    available  = [1] * NUM_RESOURCES                       # one instance per resource

    in_ready   = set()   # indices currently in ready_queue (for O(1) membership)

    def enqueue(idx):
        if idx not in in_ready and idx not in completed:
            ready_queue.append(idx)
            in_ready.add(idx)

    # -----------------------------------------------------------------------
    # Main simulation loop
    # -----------------------------------------------------------------------
    while len(completed) < n:

        # 1. Admit newly arrived processes
        for i, p in enumerate(processes):
            if (p.arrival_time <= current_time
                    and i not in completed
                    and i not in in_ready
                    and i not in waiting_queue):
                last_ready_time[i] = current_time
                enqueue(i)

        # 2. Check I/O completions
        for entry in list(io_queue):
            idx, io_end = entry
            if current_time >= io_end:
                io_queue.remove(entry)
                last_ready_time[idx] = current_time
                enqueue(idx)

        # 3. Check if any blocked (waiting_queue) process can now be granted its resource
        for idx in list(waiting_queue.keys()):
            rid = waiting_queue[idx]
            if available[rid] > 0:
                print(f"  Time {current_time}: Resource R[{rid}] now available -> "
                      f"unblocking P{processes[idx].pid}")
                allocate(idx, rid, allocation, need)
                # need[idx][rid] was set when blocked; clear it on grant
                need[idx][rid]  = 0
                del waiting_queue[idx]
                last_ready_time[idx] = current_time
                enqueue(idx)

        # 4. Deadlock detection (only among blocked processes)
        if waiting_queue:
            active = set(waiting_queue.keys())
            deadlocked = detect_deadlock(allocation, need, available, active)
            if deadlocked:
                print(f"\n*** Deadlock detected at time {current_time}! "
                      f"Deadlocked PIDs: {[processes[i].pid for i in deadlocked]} ***")
                # Terminate the lowest-priority deadlocked process (highest priority number)
                victim = max(deadlocked, key=lambda i: (processes[i].priority, processes[i].arrival_time))
                print(f"    Terminating P{processes[victim].pid} to recover.")
                release_all(victim, allocation, available)
                need[victim] = [0] * NUM_RESOURCES
                if victim in waiting_queue:
                    del waiting_queue[victim]
                completed.add(victim)
                finish_time[victim]      = current_time
                turnaround_time[victim]  = current_time - processes[victim].arrival_time
                gantt_chart.append((current_time, f"P{processes[victim].pid}(killed)", current_time))
                continue   # re-evaluate this time step

        # 5. Idle if nothing is ready
        if not ready_queue:
            gantt_chart.append((current_time, "Idle", current_time + 1))
            print(f"Time {current_time}: CPU idle")
            current_time += 1
            continue

        # 6. Sort ready queue by (priority, arrival_time) — stable priority scheduling
        sorted_rq = sorted(ready_queue,
                           key=lambda i: (processes[i].priority, processes[i].arrival_time))
        ready_queue = deque(sorted_rq)

        idx     = ready_queue.popleft()
        in_ready.discard(idx)
        process = processes[idx]

        # Accumulate waiting time (time spent in ready queue since last enqueue)
        waiting_time[idx] += current_time - last_ready_time[idx]

        step = process.current_step()
        if step is None:
            # Process is fully done
            completed.add(idx)
            finish_time[idx]      = current_time
            turnaround_time[idx]  = current_time - process.arrival_time
            print(f"Time {current_time}: P{process.pid} finished.")
            continue

        print(f"\nTime {current_time}: P{process.pid} running step {step}")

        # ------------------------------------------------------------------
        if step.step_type == StepType.CPU:
            run = min(step.remaining, quantum)
            gantt_chart.append((current_time,
                                f"P{process.pid}(CPU)",
                                current_time + run))
            print(f"  CPU burst: running {run} / {step.remaining} units")
            current_time    += run
            step.remaining  -= run
            if step.remaining == 0:
                process.advance_step()
            # Preempt if more work remains and there are other ready processes
            if process.current_step() is not None:
                last_ready_time[idx] = current_time
                enqueue(idx)

        # ------------------------------------------------------------------
        elif step.step_type == StepType.IO:
            io_end = current_time + step.value
            gantt_chart.append((current_time,
                                f"P{process.pid}(IO)",
                                io_end))
            print(f"  IO burst: {step.value} units, done at time {io_end}")
            io_queue.append((idx, io_end))
            process.advance_step()
            # Do NOT re-enqueue; process will be re-admitted when IO finishes

        # ------------------------------------------------------------------
        elif step.step_type == StepType.REQUEST:
            rid = step.value
            print(f"  Requesting R[{rid}] (available={available[rid]})")
            if available[rid] > 0:
                allocate(idx, rid, allocation, available)
                print(f"  R[{rid}] granted immediately.")
                process.advance_step()
                last_ready_time[idx] = current_time
                enqueue(idx)
            else:
                # Block the process
                need[idx][rid] = 1
                waiting_queue[idx] = rid
                print(f"  R[{rid}] unavailable -> P{process.pid} blocked.")
            current_time += 1   # request takes 1 time unit

        # ------------------------------------------------------------------
        elif step.step_type == StepType.RELEASE:
            rid = step.value
            release(idx, rid, allocation, available)
            print(f"  Released R[{rid}] (now available={available[rid]})")
            process.advance_step()
            last_ready_time[idx] = current_time
            enqueue(idx)
            current_time += 1   # release takes 1 time unit

        # ------------------------------------------------------------------
        # Check if process just finished all steps
        if process.current_step() is None and idx not in completed and idx not in in_ready:
            completed.add(idx)
            finish_time[idx]     = current_time
            turnaround_time[idx] = current_time - process.arrival_time
            in_ready.discard(idx)
            print(f"  P{process.pid} completed all steps at time {current_time}.")

    # -----------------------------------------------------------------------
    # Results
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("GANTT CHART")
    print("=" * 60)
    for start, label, end in gantt_chart:
        bar = "#" * max(1, end - start)
        print(f"  [{start:4d} - {end:4d}]  {label:20s}  {bar}")

    print("\n" + "=" * 60)
    print("PROCESS METRICS")
    print("=" * 60)
    print(f"{'PID':>5} {'Arrival':>8} {'Finish':>8} {'Turnaround':>12} {'Waiting':>10}")
    for i, p in enumerate(processes):
        print(f"  {p.pid:3d}   {p.arrival_time:6d}   {finish_time[i]:6d}   "
              f"{turnaround_time[i]:10d}   {waiting_time[i]:8d}")

    avg_wt  = sum(waiting_time)     / n
    avg_tat = sum(turnaround_time)  / n
    print(f"\nAverage Waiting Time   : {avg_wt:.2f}")
    print(f"Average Turnaround Time: {avg_tat:.2f}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

TEST_CASES = {
    "1": {
        "name": "Priority Scheduling",
        "desc": "P1 (priority 1) runs first, then P2, then P3",
        "lines": [
            "1 0 1 CPU{10}",
            "2 0 2 CPU{5}",
            "3 0 3 CPU{8}",
        ]
    },
    "2": {
        "name": "Round Robin",
        "desc": "Equal-priority processes share CPU in time slices",
        "lines": [
            "1 0 1 CPU{10,5,8}",
            "2 0 1 CPU{6,4}",
        ]
    },
    "3": {
        "name": "I/O Burst Handling",
        "desc": "P1 blocks for I/O, P2 runs meanwhile, P1 returns",
        "lines": [
            "1 0 1 CPU{5} IO{4} CPU{3}",
            "2 2 1 CPU{4} IO{2} CPU{6}",
        ]
    },
    "4": {
        "name": "Resource Allocation (No Deadlock)",
        "desc": "P1 uses R1, P2 uses R2 — no conflict, both complete",
        "lines": [
            "1 0 1 CPU{R[1],5,F[1]}",
            "2 0 2 CPU{R[2],4,F[2]}",
        ]
    },
    "5": {
        "name": "Deadlock Detection & Recovery",
        "desc": "P1 holds R1 waits R2; P2 holds R2 waits R1 -> deadlock -> P2 killed",
        "lines": [
            "1 0 1 CPU{R[1],10,R[2],5,F[1],F[2]}",
            "2 0 2 CPU{R[2],10,R[1],5,F[2],F[1]}",
        ]
    },
    "6": {
        "name": "Full System Test",
        "desc": "Priority + Round Robin + I/O + Resources + Deadlock all together",
        "lines": [
            "1 0 1 CPU{R[1],10,R[2],5,F[1],F[2]}",
            "2 2 2 CPU{5} IO{3} CPU{R[2],4,F[2]}",
            "3 4 0 CPU{8,R[1],6,F[1]}",
        ]
    },
}


def run_test_case(tc_num, quantum=10):
    tc = TEST_CASES[tc_num]
    print("\n" + "=" * 60)
    print(f"TEST CASE {tc_num}: {tc['name']}")
    print(f"  {tc['desc']}")
    print("=" * 60)

    processes = []
    for line in tc["lines"]:
        parts = line.strip().split()
        pid, arrival, priority = int(parts[0]), int(parts[1]), int(parts[2])
        burst_str = " ".join(parts[3:])
        p = Process(pid, arrival, priority)
        p.steps = parse_steps(burst_str)
        processes.append(p)

    print("\nProcesses:")
    for p in processes:
        print(f"  P{p.pid}  arrival={p.arrival_time}  priority={p.priority}  steps={p.steps}")
    print()

    round_robin_priority(processes, quantum)


def main():
    import sys

    quantum = 10

    # Run directly with a file: python3 main.py myfile.txt
    if len(sys.argv) == 2 and not sys.argv[1].isdigit():
        filename = sys.argv[1]
        print(f"Reading from file: {filename}")
        processes = parse_input_file(filename)
        print("=" * 60)
        print("PARSED PROCESSES")
        print("=" * 60)
        for p in processes:
            print(f"  P{p.pid}  arrival={p.arrival_time}  priority={p.priority}")
            print(f"    steps: {p.steps}")
        print()
        round_robin_priority(processes, quantum)
        return

    # Run a specific test case: python3 main.py 5
    if len(sys.argv) == 2 and sys.argv[1].isdigit():
        tc = sys.argv[1]
        if tc not in TEST_CASES:
            print(f"Unknown test case '{tc}'. Choose 1-6.")
            return
        run_test_case(tc, quantum)
        return

    # Interactive menu
    print("\n" + "=" * 60)
    print("  CPU SCHEDULING + DEADLOCK DETECTION SIMULATOR")
    print("=" * 60)
    print("\nAvailable test cases:\n")
    for num, tc in TEST_CASES.items():
        print(f"  [{num}] {tc['name']}")
        print(f"       {tc['desc']}")
    print(f"  [A] Run ALL test cases")
    print(f"  [Q] Quit")
    print()

    choice = input("Select test case (1-6 / A / Q): ").strip().upper()

    if choice == "Q":
        return
    elif choice == "A":
        for num in TEST_CASES:
            run_test_case(num, quantum)
    elif choice in TEST_CASES:
        run_test_case(choice, quantum)
    else:
        print(f"Invalid choice '{choice}'.")


if __name__ == "__main__":
    main()
