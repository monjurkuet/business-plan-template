# TikTok 404 Redirect Fix — Investigation & Plan

**Date:** July 4, 2026  
**Codebase:** `/root/codebase/sm-auto/`  
**Issue:** TikTok scraper navigating to `https://www.tiktok.com/404?fromUrl=/video/7658210005107363093`

---

## Root Cause

TikTok **requires the `@username`** in the video URL. `https://www.tiktok.com/video/7658210005107363093` (no username) redirects to `/404?fromUrl=/video/7658210005107363093`.

The correct format is: `https://www.tiktok.com/@<username>/video/<video_id>`

### Where the broken URL originates

**File:** `src/storage/postgres/tiktok_persistence.ts`, lines 527-529 (FYP persistence)

```typescript
const username = video.authorUsername ?? null;
const postUrl = username
  ? `https://www.tiktok.com/@${username}/video/${video.videoId}`
  : `https://www.tiktok.com/video/${video.videoId}`;  // ← THIS LINE BROKEN
```

When `authorUsername` is `null` (from FYP DOM extraction failure), the fallback URL `/video/<id>` is written to `social_posts.post_url`. This URL redirects to 404 on TikTok.

### How it cascades

```
FYP DOM extraction → authorUsername=null
  → tiktok_persistence.ts line 529: postUrl = /video/<id> (broken)
  → INSERT into social_posts with broken post_url
  → activity_selector.ts line 1305: targetUrl = row.post_url (broken URL)
  → group_daemon.ts line 760: --url broken_url
  → tiktok_post_detail_extractor.ts line 60: page.goto(broken_url)
  → TikTok redirects to /404?fromUrl=/video/<id>
```

The existing filter at `activity_selector.ts:1291-1292` (`NOT LIKE '%/video/0'`, `NOT LIKE '%/video/1'`) catches fallback IDs but NOT the missing-username pattern — because `/video/<valid_19digit_id>` looks like a legitimate URL but TikTok rejects it without the username.

---

## Fix Plan (3 independent changes, each self-contained)

### Fix 1: FYP persistence — never write username-less URLs to social_posts

**File:** `src/storage/postgres/tiktok_persistence.ts`, lines 525-559

**Change:** Skip `social_posts` promotion when `authorUsername` is null. The `/video/<id>` fallback URL is useless — it redirects to 404.

```typescript
// Promote to social_posts only if we have a valid video ID AND author username
if (isValidVideoId && username) {
  const postUrl = `https://www.tiktok.com/@${username}/video/${video.videoId}`;
  // ... existing INSERT ...
}
```

**Effect:** FYP videos without author info stay only in `tiktok_fyp_samples` (already working). No more broken URLs entering `social_posts`.

**Risk:** Reduces post_detail candidate pool. Acceptable — better to have fewer valid than many broken entries.

**Skip if:** Fix 2 below is sufficient (it prevents consumption regardless).

---

### Fix 2: Activity selector — filter out posts missing @username in URL

**File:** `src/core/activity_selector.ts`, lines 1286-1300

**Change:** Add a WHERE filter requiring `@` in `post_url` for TikTok post_detail candidates:

```sql
AND (sp.post_url LIKE '%/@%' OR sp.post_url LIKE '%tiktok.com/@%')
```

This rejects all `/video/<id>` URLs (no username) and only passes `/@<username>/video/<id>` URLs.

**Effect:** Zero broken URLs dispatched to post_detail extractor. Existing broken rows in DB stay dormant.

**Risk:** None — pure defensive filter.

---

### Fix 3: post_detail extractor — validate URL before navigating, catch 404 redirect

**File:** `src/extractors/tiktok_post_detail_extractor.ts`, after line 60

**Change:** After `page.goto()`, check `window.location.href` for 404 pattern and bail early with a clean error:

```typescript
// After goto, before waiting for selectors
const finalUrl = await page.evaluate(() => window.location.href);
if (finalUrl.includes('/404') || finalUrl.includes('fromUrl')) {
  return {
    data: { /* empty result with platform/tiktok */ },
    artifacts: { error: '404_redirect', inputUrl: input.postUrl, finalUrl }
  };
}
```

**Effect:** 404 redirects caught immediately, no wasted 15s waitForSelector timeout, clean error logged.

**Risk:** None — early bail.

---

## Priority & Effort

| # | Fix | Lines | Effort | Priority |
|---|-----|-------|--------|----------|
| 1 | FYP persistence — require username | ~2 | 5 min | High (stops source) |
| 2 | Activity selector — filter @ in URL | ~1 | 2 min | High (defensive, simplest) |
| 3 | Post detail — detect 404 early | ~8 | 5 min | Medium (handles remaining cases) |

**Recommended:** Fix 2 first (simplest, immediate effect), then Fix 1 (prevent future), then Fix 3 (graceful handling of edge cases).

---

## Verification

```sql
-- After Fix 1+2 deployed: should be ZERO username-less post_urls dispatched
SELECT COUNT(*) FROM scraper.social_posts
WHERE platform = 'tiktok'
  AND is_deleted IS NOT TRUE
  AND post_url NOT LIKE '%/@%'
  AND last_post_detail_at IS NULL;
```

```bash
# Manual test: extractor should bail on missing-username URL
bun run /root/codebase/sm-auto/src/cli/scrape_tiktok_post_detail.ts \
  --url 'https://www.tiktok.com/video/7658210005107363093' \
  --chrome-port 9222 --browser-id test --max-scrolls 1 2>&1 | tail -5
```

---

## Related (out of scope for this fix, noted for future)

- **authorUsername extraction failure rate**: FYP DOM extraction lacks `@username` on ~half of videos. The `mergeApiIntoDomVideos` fallback (line 98-116) fills from API response but only when API captures fire. This is a separate DOM-selector hardening issue (covered in `/root/ig-tiktok-fix-plan.md` Phase 1A).
- **following_feed + discover persistence**: Both have no-op persistence that doesn't even UPSERT social_posts. Not related to this 404 bug, but limits data flow.