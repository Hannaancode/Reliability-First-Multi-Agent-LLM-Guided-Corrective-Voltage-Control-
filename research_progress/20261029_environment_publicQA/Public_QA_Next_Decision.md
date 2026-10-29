# Exact public QA prompt contract

All 150 no-tool prompts are now packaged and independently reconstructed byte for byte from the pinned author runner, native circuit description and previously admitted question/option views. Source order is unchanged. The circuit has four generators, four loads and nine lines. The participant prompts contain no answer key, reference OPF solution, explanation, category or difficulty metadata. Their lengths are 1,758–1,840 characters; these are not tokenizer counts.

This closes prompt construction, not model execution. No hosted model, GPU assignment, PF, OPF, training or scientific inference was invoked. The original runner, agent and tools modules were not imported or executed; only the reviewed pure prompt/parser functions were extracted from their ASTs. An independent script reconstructed every prompt without importing the producer. Raw third-party source, circuit and participant question text remain local.

The actual runner's `extract_final_letter` selects the **last standalone uppercase A–D**, then falls back to `evaluator.extract_letter`. This supersedes treating the standalone evaluator as the complete primary parser in the earlier admission note. For example, synthetic `A then D` produces D in the runner and A in the standalone evaluator. The native fallback still maps synthetic `I cannot answer` to C. No actual model answers were evaluated and no outcome-dependent scoring change occurred. A faithful comparison must preserve the complete native runner parser as primary and freeze strict letter-only validity as a separate secondary diagnostic.

The no-tool runner creates an empty per-question workspace, sends the complete circuit and question, and requests ask mode. The instruction prohibits tools, but no-tool enforcement still needs an actual runtime boundary. The source records only the first 400 characters of the answer after parsing the full answer. Our future implementation should preserve the full raw answer and separately retain that native report field. It must report any departure from the author CLI, version, token accounting or timeout contract. Author no-tool timeout defaults to 300 seconds; it may be overridden by the environment, so this is not proof of each historical run's actual limit.

The source's code-generation mode makes two model calls around a script execution, and the agent mode allows a tool loop. Their scores cannot be pooled with no-tool results. The original RAG or voltage-control adapter is not automatically an equivalent model in any of these modes.

Next required work:

1. Recover the exact RAG base model, retrieval/index and generation contract from supplied notebooks and preserved outputs. Initial static inspection finds Qwen2.5-0.5B-Instruct and Llama-3.2-1B-Instruct variants; it does not establish which complete runtime produced every paper score. Keep this separate from the private voltage-command LoRA.
2. Define any new 0.5B/1.5B/3B public-model QA scale comparison as a prospective transfer study with fixed full150 inputs, no tuning on labels, one outcome per model/item, exact revisions, same decoding/output policy, complete costs and same-information controls. It would not be a repeat or rescue of the stopped voltage-control scale intervention, nor proof of the original RAG system's performance.
3. Verify actual local tokenizer capacity, model revision/license/access, causal chat-template rendering, cold loader/memory, immutable source and persistent output journal before allocation. Do not infer available GPU hours from historical accounts.
4. Keep any complete RAG arm separate: admissible retrieval corpus, duplicate/answer leakage audit, identical external information for controls and actual index revision are necessary before attributing RAG benefit.

The broad research goals remain open. Input and parser correctness remove a comparison error; they do not establish a winning model or novel method.
