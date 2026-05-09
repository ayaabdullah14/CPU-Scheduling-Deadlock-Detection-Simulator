# CPU Scheduling + Deadlock Detection Simulator

## Overview

Simulates an operating system scheduler with:

- **Priority Scheduling** — lower number = higher priority
- **Round Robin** — equal-priority processes share the CPU via time quantum
- **I/O Bursts** — processes block for I/O and return to the ready queue
- **Resource Allocation** — one instance per resource; processes request and release
- **Deadlock Detection** — Banker's-style safety algorithm detects circular waits
- **Deadlock Recovery** — lowest-priority deadlocked process is terminated

---

## How to Run

```bash
python3 main.py
```

The scheduler reads `processes.txt` by default. Change the filename or quantum at the bottom of `main.py`:

```python
filename = "processes.txt"
quantum  = 10
```

---

## Input File Format

Each line is one process:

```
PID  ARRIVAL_TIME  PRIORITY  BURSTS
```

| Field | Description |
|---|---|
| PID | Unique process ID (integer) |
| ARRIVAL_TIME | Time the process enters the system |
| PRIORITY | Lower number = higher priority |
| BURSTS | Sequence of CPU/IO/resource steps (see below) |

---

## Burst Syntax

All burst steps live inside `CPU{...}` or `IO{...}` blocks.
Items inside a block are executed **left to right in order**.

### CPU burst — plain execution time

```
CPU{15}
```

Runs for 15 time units (subject to preemption by the quantum).

### CPU burst — multiple sequential durations

```
CPU{10,5,8}
```

Three separate CPU steps: 10 units, then 5, then 8.

### CPU burst — with resource request and release

```
CPU{R[1],15,R[2],10,F[1],F[2]}
```

Step-by-step:
1. Request resource R1
2. Run for 15 units
3. Request resource R2
4. Run for 10 units
5. Release R1
6. Release R2

`R[x]` = request resource x  
`F[x]` = release resource x  
Resource IDs are integers starting at 1.

### IO burst

```
IO{4}
```

Process blocks for 4 time units, then re-enters the ready queue.

### Mixed example (CPU + IO + CPU with resource)

```
CPU{5} IO{3} CPU{R[2],4,F[2]}
```

1. Run CPU for 5 units
2. Do I/O for 3 units
3. Request R2 → run 4 units → release R2

---

## Full Input Example

```
1 0 1 CPU{R[1],10,R[2],5,F[1],F[2]}
2 2 2 CPU{5} IO{3} CPU{R[2],4,F[2]}
3 4 0 CPU{8,R[1],6,F[1]}
```

---

## Output

The simulator prints step-by-step execution, then a summary:

```
============================================================
GANTT CHART
============================================================
  [   0 -  10]  P3(CPU)               ##########
  [  10 -  18]  P3(CPU)               ########
  ...

============================================================
PROCESS METRICS
============================================================
  PID  Arrival   Finish   Turnaround    Waiting
    1        0      86           86        61
    2        0      73           73        67
    3        0      50           50         0

Average Waiting Time   : 42.67
Average Turnaround Time: 69.67
```

### Metrics Explained

| Metric | Formula |
|---|---|
| Turnaround Time | Finish Time − Arrival Time |
| Waiting Time | Time spent in ready queue (not running, not in I/O) |

---

## Deadlock Handling

Deadlock is detected when a group of blocked processes are each waiting for a resource held by another process in the group (circular wait).

**Detection:** Banker's safety algorithm — attempts to find a safe execution order. If no order exists, a deadlock is declared.

**Recovery:** The blocked process with the **lowest priority** (highest priority number) is terminated. All its held resources are released immediately, unblocking the remaining processes.

Example deadlock scenario:

```
P1 holds R1, requests R2
P2 holds R2, requests R1
→ Deadlock! P2 (lower priority) is terminated.
→ R2 released → P1 can proceed.
```

---

## Configuration

At the top of `main.py`:

```python
NUM_PROCESSES = 3   # maximum number of processes
NUM_RESOURCES = 3   # number of distinct resources (R[1] through R[NUM_RESOURCES])
```

In `main()`:

```python
quantum = 10        # time-slice length for Round Robin
```

---

## Test Cases

Six ready-to-use test cases are provided in `test.txt`:

| # | Tests |
|---|---|
| 1 | Priority scheduling |
| 2 | Round Robin with equal priorities |
| 3 | I/O burst handling |
| 4 | Resource allocation without deadlock |
| 5 | Deadlock detection and recovery |
| 6 | Full system (all features combined) |

Copy the process lines from `test.txt` into `processes.txt` to run each case.

---

## Project Files

```
main.py        — simulator source code
processes.txt  — active input (edit this to change the scenario)
test.txt       — six documented test cases
README.md      — this file
```
