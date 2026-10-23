---
title: "Looking for the PHP upload-progress bug ourselves: what we found, and what we didn't"
date: 2026-10-21
status: draft
---

On October 21, 2026, a PHP advisory with a critical rating (CVSS v4.0 9.2) was circulating before the patch. The public write-up pointed at the session upload-progress feature. PHP hadn't published details yet, so we went looking in the source ourselves.

This post covers what we did, what we found, and what we still don't know. We haven't confirmed the bug, and nothing here is a working exploit.

## Starting point

The feature is simple to describe. When a browser uploads files, PHP can record how far the upload has got in the user's session, so a progress bar can show it. The feature is on by default. The code that does this lives in `ext/session/session.c` and is triggered by the multipart parser in `main/rfc1867.c`.

Reading that code shows the main concern. Session data is written while the multipart body is still being parsed, and there is no login check at that point. The session ID comes from the request itself, through a cookie or a form field. So an anonymous request can make PHP do session work. That matches what the public write-up described.

## What we did

1. **Source review.** We read the callback that handles upload-progress events. Two spots keep raw pointers into hash tables across later changes. Those are the first places to check for memory errors.
2. **Static analysis.** We ran Semgrep's public C ruleset over the full PHP 8.5.12 tree. It returned zero findings, but it also failed to parse the session files, so the result tells us nothing about the session code. We report that as inconclusive, not as clean.
3. **A debug build with AddressSanitizer.** AddressSanitizer is a tool that reports the exact moment memory is misused. We built PHP 8.5.12 with it, enabling only the session extension.
4. **Benign tests.** Normal uploads with a session ID wrote session files and produced no reports.
5. **Fuzzing.** We sent 2,000 randomized, often malformed multipart requests to the local build. Random boundaries, truncated bodies, early disconnects, and odd session IDs.

## What we found

One request sequence crashes the build. The crash happens at request 1,710 of a fixed sequence, and it reproduces every time with the same seed. The crash shows up in the cleanup step of the upload-progress code, at the point where PHP starts the session again.

The allocator, PHP's memory manager, found that its own bookkeeping was damaged. That usually means some memory was written after it was freed, or a write ran past the end of a buffer. The damage was done by an earlier request in the sequence, not the one that crashed.

When we switched PHP to the system allocator, the same sequence runs without a crash and AddressSanitizer reports nothing. Our best reading is that the bad write lands inside PHP's own memory arena, which AddressSanitizer doesn't instrument. We haven't proved that yet.

Single requests don't crash on their own, so the bug needs earlier requests to set things up.

## What we don't know

- **We haven't found the write.** We know where the damage shows up, not what caused it. Finding that needs a minimal reproducer and a memory checker that can see inside PHP's arena.
- **Whether this is the published bug.** The public description is disputed, and PHP's advisory isn't out yet. We won't call this the CVE until the root cause matches the advisory.
- **One unexplained stop.** The server stopped once at request 570 with no report. We haven't looked into it.

## What to do now

You don't need to wait for the investigation to act. Upload progress can be disabled with a single setting, `session.upload_progress.enabled = 0`, and multipart requests can be blocked on sites that don't take uploads. Both are described in the early mitigation write-up linked below. Those changes are safe to make today and cost little.

- Source write-up: https://ma.ttias.be/php-cve-2026-109618-early-mitigation/
- Check PHP's official advisory on php.net, and the CVE records, for the fixed versions.

We'll update this post when we find the write or when PHP publishes its advisory.
