# Independent legal review protocol

Status: **PENDING EXTERNAL SIGN-OFF**

This protocol covers the 31 criteria in Experiment 3 and the 13 criteria in
Experiment 4. A review conclusion applies only to the exact files and criterion
records identified in the accompanying legal-reliability manifest. It does not
approve the entire database, a model result, or a formal experiment.

## 1. Freeze the review object

Before review, record the manifest filename and SHA-256 from its companion
`.sha256` file. The manifest must list each task's exact `as_of`, every criterion
ID, the hashes of the criterion and task context, and the hashes of every
included builder, generated dataset, matter file, source-check file and
checklist. A Git commit alone is insufficient because the review may concern
uncommitted working-tree content.

The generated Experiment 3 and Experiment 4 checklists are frozen, blank,
read-only templates. The reviewer must not fill or sign those files in place.
Findings and signatures go in a separate completed-response artifact outside
the frozen input set. That response must identify the original manifest and
SHA-256 and reproduce the relevant task, criterion and source hashes. A signed
response is an output of the review, not an input to the manifest it signs.

Each decision, determination and legislative version must remain a separate
source record. Parallel reports of the same decision may share a record;
different procedural decisions may not. A phrase found in one source cannot be
used to verify another source.

## 2. Reviewer declaration

The reviewer records:

- name, institution and contact details;
- relevant Hong Kong legal or academic qualification and how it was checked;
- subject experience and working language(s);
- any role in writing this library, the matter files, builders or answer keys;
- any relationship with the project, funder, cited proceedings or model
  supplier;
- whether the reviewer saw model answers or experimental conditions; and
- any AI or other research-assistance tools used.

Conflict status must be one of: pending assessment, no known conflict,
disclosed and managed, or recused. Record the assessor, decision, safeguards and
date. The independent signatory must not have written this library or any of
the reviewed matter files, builders or answer keys. Merely assigning that
person a criterion written by somebody else does not establish independence.
Qualification verification and the conflict assessment must both be complete.
Only `no known conflict`, or `disclosed and managed` with recorded safeguards,
can support a pass; `pending assessment` and `recused` cannot. An AI review does
not count as independent external legal review.

## 3. Review every criterion separately

For each criterion, the reviewer must use the corresponding generated reader
checklist as a read-only template and record the following in the separate
completed-response artifact:

1. **Object:** experiment, task and criterion ID; full proposition; task facts;
   exact `as_of`; polarity; discriminator; task-context and criterion hashes.
2. **Sources:** complete title and citation; court and procedural nature, or
   legislative title, chapter and version; official link; local-file hash;
   decision/version and availability dates. If a date is a proxy, say so.
3. **Reading:** exact paragraph, page or section; necessary surrounding text;
   whether the reviewer read the original source, an extract, or a later
   decision quoting it; and any unavailable material.
4. **Legal assessment:** whether the source supports the full proposition;
   conditions, exceptions and factual limits; ratio, obiter, leave decision,
   majority or separate reasons; contrary and later authority; and suitability
   for the stated historical cutoff.
5. **Answer-key assessment:** whether the synthetic task facts support the
   expected answer, whether the discriminator is fair, and whether another
   legally reasonable answer should pass.
6. **Outcome:** supports current text, rewrite and re-review required,
   unsupported, insufficient evidence, recused, or not reviewed. Give reasons
   and identify any required correction or withdrawal.
7. **Sign-off:** reviewer identity, recusal decision, actual UTC time and
   signature or traceable approval record, bound to the recorded task,
   criterion and source hashes.

Only “supports current text” counts as a pass. Mechanical identity, date and
phrase checks do not establish legal support.

## 4. Change and withdrawal rules

A change to a proposition, matter fact, cutoff, polarity, discriminator,
source, source mapping or relevant passage invalidates the affected sign-off.
Create a new manifest version. An earlier review may be carried forward only if
the reviewer checks the dependency comparison and expressly confirms the
unchanged item against the new manifest. The final package sign-off must always
refer to the new manifest.

Creating or signing a completed-response artifact does not change the frozen
inputs and does not require regenerating the manifest that it signs. Give the
response its own SHA-256. If the review adds a source, changes an input, or
corrects a key, save that material with its identity, retrieval information and
hash and create a new manifest version before signing the revised package.

If a material omission, contrary authority, source error or undisclosed conflict
is found, suspend reliance on the affected criteria and record the scope,
reason, owner and next action. Keep earlier decisions as history; do not
overwrite them. Hashes establish content identity, not legal correctness or
source authenticity.

## 5. Final package sign-off

The reviewer lists the accepted IDs, rewritten/unsupported/excluded IDs,
remaining issues, limitations and the exact manifest SHA-256, then signs and
dates the separate response. The response also records how the reviewer's
qualification was verified, the completed conflict decision, contact details,
actual source-reading type, any model-answer exposure and any research tools.
The statement “this version completed independent legal review” may be used
only if all 44 criteria pass, the qualification check is complete and every
conflict decision permits review. A pending, recused, unsupported, insufficient
or unreviewed item cannot count as a pass. A partial result must give the exact
passed count and scope.

## 6. Scope of the frozen evidence

Experiment 4's manifest has nine task-source associations binding seven
distinct local source-check extracts; those extracts are not complete copies of
the judgments or legislation.
Experiment 3's citations and pins are bound inside its tasks, checklist and
criterion hashes, but the manifest contains no separate Experiment 3 original-
source records. The reviewer must retrieve the official originals, record what
was actually read and preserve the source identity, retrieval information and
hash in the completed response. Any resulting key correction requires a new
manifest version.

The manifest freezes the named core data inputs, builders and generated outputs
only. It does not turn the local extracts into authenticated originals, approve
the entire database, or freeze model outputs and human grading records that do
not yet exist.

Legal proposition review is separate from human answer-grading calibration,
model-identity assurance, scoring-weight calibration, complete historical-law
reconstruction and approval of a formal statistical protocol. None of those
states, including `formal_readiness`, changes automatically when this review is
signed.
