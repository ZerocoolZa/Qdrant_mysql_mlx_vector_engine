#[@GHOST]{file_path="Dom_DecisionTrees/question_recursion_framework.md" date="2026-08-18" author="Devin" session_id="question-recursion" context="Recursive question framework — keep asking until the problem space collapses to zero uncertainty"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE BCL-in BCL-out Run dispatch no-print"}
#[@FILEID]{id="question_recursion_framework.md" domain="Dom_DecisionTrees" authority="QuestionRecursion"}
#[@SUMMARY]{summary="Recursive question-asking framework — each answer spawns new questions until uncertainty reaches zero"}
#[@CLASS]{class="QuestionRecursion" domain="Dom_DecisionTrees" authority="single"}
#[@METHOD]{method="Generate" type="recursive"}

# Recursive Question Framework — Collapse the Problem Space

## The principle

A question collapses ONE assumption into a fact.
A fact spawns TWO new questions (what does this mean? what follows from this?).
Each of those spawns two more.
The question tree grows EXPONENTIALLY until it hits facts that need no further questions.

The problem space is collapsed when:
- Every fact is verified
- Every assumption is either confirmed or replaced with a fact
- Every path has been traced to its end
- No new questions can be generated from the remaining facts

## The recursion

```
QUESTION 1
├── YES → FACT → QUESTION 1a, QUESTION 1b
│   ├── 1a YES → FACT → QUESTION 1a1, QUESTION 1a2
│   ├── 1a NO  → FACT → QUESTION 1a3
│   ├── 1b YES → FACT → QUESTION 1b1
│   └── 1b NO  → FACT → done (leaf)
└── NO  → FACT → QUESTION 1c
    └── 1c YES → FACT → ...
```

Each leaf is a confirmed fact. When all leaves are facts, the problem space has collapsed.

## When to STOP asking

Stop when the answer to a question does not change any decision.
If knowing the answer would not change what you do next, the question has no leverage.
Discard it. Move on.

## When to KEEP asking

Keep asking when:
- The answer changes which file you read next
- The answer changes which code path you follow
- The answer eliminates a branch of the search tree
- The answer contradicts an assumption you were about to act on
- The answer reveals a new file, table, or chat you did not know about

## The depth limit

Recursion depth is limited by:
1. **Physical reality** — the file either exists or it does not. No amount of questions changes that.
2. **Decision relevance** — if the answer does not change a decision, stop.
3. **Information availability** — if there is no way to verify, the question is unanswerable. Mark it as UNKNOWN and move on.

In practice: 3-5 levels of recursion collapses most problems.
Level 1: 15 categories x 10 questions = 150 questions
Level 2: each answer spawns 2 new questions = 300 questions
Level 3: each answer spawns 2 new questions = 600 questions
Level 4: each answer spawns 2 new questions = 1200 questions
Level 5: each answer spawns 2 new questions = 2400 questions

But most branches terminate at level 2-3 because the answer is a physical fact (file exists/does not exist).

## The algorithm

```
function collapse(problem):
    questions = generate_questions(problem)
    facts = {}
    unknowns = {}

    for q in questions:
        answer = check(q)

        if answer == YES:
            facts[q] = YES
            new_questions = follow_up_yes(q)
            questions.extend(new_questions)

        elif answer == NO:
            facts[q] = NO
            new_questions = follow_up_no(q)
            questions.extend(new_questions)

        else:
            unknowns[q] = CANNOT_VERIFY

    if len(unknowns) == 0 and no_new_questions:
        return COLLAPSED

    elif decisions_can_be_made(facts):
        return GOOD_ENOUGH

    else:
        return PARTIALLY_COLLAPSED
```

## The three possible outcomes

### 1. COLLAPSED — full certainty
Every question answered. Every fact verified. No unknowns.
The problem space is zero. You know exactly what to do.

### 2. GOOD_ENOUGH — sufficient certainty
Some questions unanswerable, but the known facts are enough to make a decision.
The problem space is small enough to act. Uncertainty is bounded and non-critical.

### 3. PARTIALLY_COLLAPSED — insufficient certainty
Too many unknowns. Cannot make a safe decision.
Must either:
- Find new information sources (fix the pb_reader, search new directories)
- Ask the user (they may know the answer)
- Accept the risk and proceed with the most likely interpretation

## Worked example — dedupe_explorer.py origin

### Level 1 — Initial questions

Q: Does the file exist? → CHECK: ls -la → YES → FACT: file exists at Cascade_toolStack/bin_tools/
Q: When was it created? → CHECK: stat → YES → FACT: Jun 28 19:05
Q: Is it in git? → CHECK: git log → YES/NO → FACT
Q: Is it in MySQL? → CHECK: SELECT → YES → FACT: 2 mentions in devin_messages (both ls output)
Q: Is it in chat_mover? → CHECK: grep → YES → FACT: referenced in CLI Error Prevention stage1
Q: Is it in Downloads? → CHECK: grep → YES → FACT: referenced in CLI Error Prevention.md
Q: Is it in .pb files? → CHECK: bcl_pb_reader → CANNOT_VERIFY (pb_reader does not parse content)

### Level 2 — Follow-up questions from Level 1 answers

From "referenced in CLI Error Prevention.md":
  Q: Did CLI Error Prevention.md CREATE it or USE it? → CHECK: read context → FACT: USED it, did not create it
  Q: What time was CLI Error Prevention.md? → CHECK: file timestamp → FACT: Jun 28 20:22 (1hr 17min after file creation)
  Q: Is there a chat export from BEFORE 19:05? → CHECK: ls -la Downloads/*.md by date → FACT: ?

From "2 mentions in devin_messages (both ls output)":
  Q: Which session do those messages belong to? → CHECK: SELECT session_id → FACT: session X
  Q: Was session X active at 19:05? → CHECK: message timestamps → FACT: ?
  Q: Did session X create the file or just list it? → CHECK: read full message → FACT: just listed it

From "cannot verify .pb files":
  Q: Can I fix bcl_pb_reader to parse content? → CHECK: read pb_reader code → FACT: yes, the code needs deep_extract_string
  Q: Should I fix it? → DECISION: yes, it is the only way to search 145 encrypted files
  Q: How long to fix? → ESTIMATE: 1 edit, 1 rebuild

### Level 3 — Follow-up questions from Level 2 answers

From "CLI Error Prevention USED it, did not create it":
  Q: Where did CLI Error Prevention get the file from? → CHECK: the chat says "another instance of Cascade" → FACT: another Cascade instance created it
  Q: Can I find that other instance? → CHECK: search .pb files from before 20:22 on Jun 28 → FACT: need pb_reader fix first

From "another Cascade instance created it":
  Q: How many Cascade instances were running on Jun 28? → CHECK: count .pb files modified on Jun 28 → FACT: ?
  Q: Which one was active at 19:05? → CHECK: .pb file timestamps → FACT: ?

### Level 4 — Follow-up from Level 3

From "need pb_reader fix":
  Q: Fix pb_reader, load all .pb, search for dedupe_explorer → ACTION
  Q: If found, which trajectory? → FACT: trajectory X
  Q: Read trajectory X content → FACT: the chat that created it

### Level 5 — Terminal

From "the chat that created it":
  Q: Does this chat match the user's memory? → ASK USER → YES → COLLAPSED
  Q: Does this chat contain the reasoning for WHY it was built? → READ → FACT

## The collapse

The problem space starts at:
- 145 .pb files
- 39 devin transcripts
- 116K devin messages
- 108K cascade questions
- Unknown number of .md exports
- Unknown number of directories

After Level 1: narrowed to "Cascade .pb files, Jun 28, before 20:22"
After Level 2: narrowed to "another Cascade instance, active at 19:05"
After Level 3: narrowed to "fix pb_reader, search .pb files"
After Level 4: narrowed to "specific trajectory"
After Level 5: COLLAPSED — the chat is found

## The meta-question

The most powerful question is not about the problem itself.
It is about the PROCESS:

**"What question, if answered, would eliminate the most other questions?"**

This is the highest-leverage question. Always ask it first.
In the dedupe_explorer case, that question was:
"Can I fix bcl_pb_reader to parse message content?"
Answering YES to that one question unlocked 145 files worth of search space.

## The anti-pattern

The WRONG approach:
- Ask 20 questions
- Get answers
- Stop
- Assume the remaining uncertainty does not matter

The RIGHT approach:
- Ask 20 questions
- Get answers
- Each answer spawns 2 new questions
- Ask those 40 questions
- Each answer spawns 2 more
- Ask those 80 questions
- Keep going until no new questions can be generated
- Or until the remaining questions have no decision leverage

## The rule

**Never stop asking while a question exists that would change a decision.**
**Stop the moment a question's answer would not change anything you do.**

This is the difference between "I think I know" and "I know".
Between "probably" and "certainly".
Between "I assume" and "I verified".

## Count

How many questions does it take to collapse a problem?
- Simple problem (1 file, 1 question): 1-3 questions
- Medium problem (1 file, 1 origin): 20-80 questions
- Complex problem (multiple files, multiple origins, multiple paths): 200-800 questions
- System-level problem (architecture, refactor, migration): 1000-5000 questions

The dedupe_explorer origin problem is MEDIUM: ~50-100 questions to full collapse.
The DecisionTreeGui refactor is COMPLEX: ~200-800 questions.
A full system migration is SYSTEM-LEVEL: ~1000-5000 questions.

## The deliverable

For any problem, the deliverable is:
1. The question tree (all questions asked, all answers received)
2. The collapsed facts (what is known with certainty)
3. The remaining unknowns (what cannot be verified)
4. The decision (what to do, based on the facts)
5. The confidence level (COLLAPSED / GOOD_ENOUGH / PARTIALLY_COLLAPSED)
