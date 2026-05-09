# CPU Scheduling + Deadlock Detection Simulator

A Python simulator that models how an operating system schedules processes and handles shared resources, including automatic deadlock detection and recovery.

---

## Features

- **Priority Scheduling** — lower priority number = higher priority
- **Round Robin** — equal-priority processes share CPU via time quantum
- **I/O Bursts** — processes block for I/O and automatically return to the ready queue
- **Resource Allocation** — one instance per resource; processes request and release
- **Deadlock Detection** — Banker's safety algorithm detects circular waits
- **Deadlock Recovery** — lowest-priority deadlocked process is terminated

---

## Files

```
main.py              — simulator source code
test.txt             — 6 ready-to-run test cases
processes.txt        — your custom input file
deadlock_test.txt    — dedicated deadlock scenario (equal-priority processes)
README.md            — this file
```

---

## How to Run

### Option 1 — Interactive menu (reads test.txt automatically)
```
python main.py
```

### Option 2 — Pass test.txt directly (shows selection menu)
```
python main.py test.txt
```
Then type a number `1`–`6`, `A` to run all, or `Q` to quit.

### Option 3 — Run a built-in test case by number directly
```
python main.py 1
python main.py 5
```

### Option 4 — Run your own input file
```
python main.py processes.txt
python main.py deadlock_test.txt
```

---

## Input File Format

Each line is one process:

```
PID  ARRIVAL_TIME  PRIORITY  BURSTS
```

| Field | Description |
|---|---|
| PID | Unique integer process ID |
| ARRIVAL_TIME | Time the process enters the system |
| PRIORITY | Lower number = higher priority |
| BURSTS | Sequence of CPU/IO/resource steps |

---

## Burst Syntax

All steps are written inside `CPU{...}` or `IO{...}` blocks and executed **left to right in order**.

### Plain CPU burst
```
CPU{15}
```
Run for 15 time units (preemptible by quantum).

### Multiple CPU durations
```
CPU{10,5,8}
```
Three sequential CPU steps: 10 → 5 → 8 units.

### CPU burst with resource request and release
```
CPU{R[1],15,R[2],10,F[1],F[2]}
```
Executes in order:
1. Request resource R1
2. Run 15 CPU units
3. Request resource R2
4. Run 10 CPU units
5. Release R1
6. Release R2

`R[x]` = request resource x  
`F[x]` = release resource x

### IO burst
```
IO{4}
```
Process blocks for 4 time units, then returns to the ready queue.

### Mixed example
```
CPU{5} IO{3} CPU{R[2],4,F[2]}
```
Run 5 CPU units → block 3 units for I/O → request R2 → run 4 units → release R2.

---

## Full Input Example

```
1 0 1 CPU{R[1],10,R[2],5,F[1],F[2]}
2 2 2 CPU{5} IO{3} CPU{R[2],4,F[2]}
3 4 0 CPU{8,R[1],6,F[1]}
```

---

## Test Cases

Six test cases are included in `test.txt`:

| # | Name | What it tests |
|---|---|---|
| 1 | Priority Scheduling | P1→P2→P3 run in strict priority order |
| 2 | Round Robin | Equal-priority processes alternate every quantum |
| 3 | I/O Burst Handling | Process blocks for I/O, another runs, first returns |
| 4 | Resource Allocation (No Deadlock) | P1 uses R1, P2 uses R2 — no conflict |
| 5 | Deadlock Detection & Recovery | Priority prevents interleaving — no deadlock triggers |
| 6 | Full System Test | All features together — deadlock triggered and recovered |

> **To force a real deadlock:** use `deadlock_test.txt` which gives both processes equal priority so they interleave while holding resources:
> ```
> 1 0 1 CPU{R[1],5,R[2],5,F[1],F[2]}
> 2 0 1 CPU{R[2],5,R[1],5,F[2],F[1]}
> ```
> P1 holds R1 and waits for R2. P2 holds R2 and waits for R1. Circular wait → deadlock detected → P2 terminated.

---

## Output

The simulator prints step-by-step execution, a Gantt chart, and a metrics table.

```
============================================================
GANTT CHART
============================================================
  [   0 -   10]  P1(CPU)               ##########
  [  10 -   15]  P2(CPU)               #####
  [  15 -   23]  P3(CPU)               ########

============================================================
PROCESS METRICS
============================================================
  PID  Arrival   Finish   Turnaround    Waiting
    1        0       10           10          0
    2        0       15           15         10
    3        0       23           23         15

Average Waiting Time   : 8.33
Average Turnaround Time: 16.00
```

### Metrics

| Metric | Formula |
|---|---|
| Turnaround Time | Finish Time − Arrival Time |
| Waiting Time | Time spent in ready queue (not running, not in I/O) |

---

## Deadlock Handling

**Detection:** Banker's safety algorithm checks if a safe execution order exists among all blocked processes. If none exists, a deadlock is declared.

**Recovery:** The blocked process with the lowest priority (highest priority number) is terminated. All its held resources are released immediately, unblocking the remaining processes.

**Example:**
```
P1 holds R1, requests R2   ──┐
P2 holds R2, requests R1   ──┘  circular wait = deadlock

→ P2 (lower priority) is terminated
→ R2 released → P1 unblocked → P1 completes
```

---

## Configuration

At the top of `main.py`:

```python
NUM_PROCESSES = 3    # maximum number of processes tracked
NUM_RESOURCES = 3    # number of distinct resources (R[1] through R[3])
```

Inside `main()`:

```python
quantum = 10         # time-slice length for Round Robin
```

---

## Verified Output — All 6 Test Cases

| # | Avg Waiting Time | Avg Turnaround Time | Deadlock? |
|---|---|---|---|
| 1 — Priority | 8.33 | 16.00 | No |
| 2 — Round Robin | 12.50 | 29.00 | No |
| 3 — I/O Handling | 1.50 | 12.00 | No |
| 4 — Resources | 5.50 | 10.00 | No |
| 5 — Deadlock scenario | 13.50 | 28.50 | No (priority prevents interleaving) |
| 6 — Full System | 10.67 | 27.00 | **Yes — P3 killed at time 20** |
