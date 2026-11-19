# Daily planner — FanartDesignsMX Reels & Carousels

Owner: Arturo (FanartDesignsMX, Etsy shop 66814655, IG @fanartdesignsmx, FB Page "Fanart Designs MX").
The GitHub Action `pipeline.yml` renders and publishes whatever is in `queue/`. The planner (a daily
Claude task) only curates designs and writes the queue. Never publish anything by other means.

## Hard rules (from Arturo)
1. **Never post a design that exists as an official Pokémon card (by ARTWORK, not by attacks).**
   Card text/attacks do NOT matter. What matters: the design must not exist on official Pokémon sources.
   Check every design with the review tool before using it: push `review/request.json`
   (`{"candidates":[{"key","name","pokemon","dex","image"}]}`), wait for the "Real-card review sheets"
   workflow, read `review/out/_summary.json` and `review/out/<key>.json` (top matches with inliers).
   The tool compares the artwork with every official card image (TCGdex: English + Japanese + TCG Pocket).
   - Any non-Pocket official card with ≥25 inliers → **reject** (same artwork as a physical card).
   - 12–24 inliers → open `<key>_match.jpg` and decide by eye (same artwork = reject).
   - Pocket card ≥25 and no physical card ≥12 → allowed (Pocket cards don't exist physically), mark `pocket`.
   - `NO_OFFICIAL_DATA` / `ERROR` → never approve; resubmit later.
   - Also reject by eye if the card shows an official set number (e.g. "ASC 294/217"), an official
     illustrator name other than Arturo Vega, or copies a famous promo (e.g. Van Gogh Pikachu).
2. **Never say Arturo designed a TCG Pocket card** — those designs belong to someone else.
   A design is "pocket" if its artwork matches a Pocket card OR its name + attacks are a Pocket card
   (web-search the attack name + "TCG Pocket"; TCGdex is missing the newest Pocket sets).
   For pocket designs use neutral wording ("this Pocket-only card, now physical", "handmade proxy").
   Only designs with `"own": true` in `catalog/designs.json` (fan-made, no official card anywhere) may
   say "I designed / my own design". When unsure, use neutral wording.
3. **Watermark always**: reels get the diagonal "Fanart Designs MX" overlay automatically; carousel image
   slides use the Cloudinary text overlay URL; collage slides are watermarked by the pipeline.
4. **No repeats**: never the same Pokémon twice within 14 days (all formats), never the same design twice.
5. **Pick Pokémon by popularity** using `catalog/popular.json` (weighted random: tier1 5, tier2 3, other 1).
   Design sources: Cloudinary folder "2000" (`<dex>_<Name>_<n>`, e.g. 25_Pikachu_27 — preferred, these
   are Arturo's watermarked mockups; search with the AnythingMCP Cloudinary search tool, expression
   `public_id:<dex>_<Name>*`) or Etsy listing images (Etsy connector, read-only).
6. Subtitles: approved Mega Mewtwo Y style only (white with black outline, yellow keywords, no box).
7. Every post gets a **new dialogue** and a **new caption** (never reuse text). Max 5 hashtags.
   Keep the offer exact: "Buy 2+ cards, save 25% with code 25OFF". Always include
   "Fan-made art card. Not an official Pokémon / Nintendo product."
8. **Carousel = exactly 4 slides, square like Arturo's past carousels**:
   (1) `{"hero": design URL}` — ONE design only, built by the pipeline with the "Handmade Proxy Cards"
   title and the "ETSY Link in Bio" button; (2) the holo video, square crop with NO blurred background
   (URL below); (3) ONE collage image with the other approved designs of the same Pokémon (1–8 designs,
   `{"collage":[urls]}`); (4) the generic "more designs" image.
9. **Write "EX" in capitals in every description** (Pikachu EX, Mega Gengar EX) — never "ex".
   (The pipeline also corrects it, but write it right.)
10. **Every carousel description must read differently** — new opening, new body, new way to say the
   offer and the call to action (only the disclaimer line stays fixed). Never reuse a sentence from
   earlier queue files; vary structure too (question, story, comparison, "which one would you pick").

## Schedule (America/Mexico_City)
- Weeks 1–4 (from 2026-11-19): 3 reels + 2 carousels per day
  08:00 reel · 12:00 carousel · 14:00 reel · 18:00 carousel · 20:30 reel
- Weeks 5–8 (from 2026-12-17): 1 reel/day 14:00 + carousels Mon/Wed/Fri/Sat 18:00
- Week 9+ (from 2027-01-14): reels Mon/Tue/Thu/Fri/Sat 14:00 + carousels Wed/Sun 18:00
Adjust with insights (Mondays): more of what performs.

## Queue item formats (`queue/YYYY-MM-DD.json` → {"items": [...]})
Reel:
```
{"id":"2026-11-19-r1","type":"reel","publish_at":"2026-11-19T08:00:00-06:00",
 "pokemon":"Greninja","listing_id":4605371798,"design_key":"4605371798-1",
 "card_image":"<Etsy il_fullxfull URL of the design (watermarked mockup)>",
 "script":[{"chunks":["Hook line..."],"speed":0.98,"pause":0.3},
           {"chunks":["Every card is handmade,","holographic,","and real card size."],"speed":1.03,"pause":0.26},
           {"chunks":["Grab two or more",["and save twenty-five percent","and save 25%"],["with code twenty-five off.","with code 25OFF"]],"speed":1.05,"pause":0.3},
           {"chunks":["Link's in my bio!"],"speed":1.0,"pause":0}],
 "voice":"af_heart","speed":1.04,"variant_seed":<random int>,"music_seed":<random int>,
 "highlight":["Greninja"],
 "caption_ig":"... link in bio ...","caption_fb":"... https://www.etsy.com/listing/<id> ..."}
```
Voices to rotate: af_heart, af_bella, am_michael, am_fenrir, bf_emma, af_heart+af_bella.
Script: 12–16 s total, 4 sentences: hook (varied: question, challenge, "you won't find this in any
booster pack", etc.), product (handmade · holographic · real card size, reworded), offer (exact numbers),
CTA (link in bio). No authorship claim unless the design is `"own": true` (rule 2).
Spell numbers in the spoken part and give the display form as [spoken, display].

Carousel:
```
{"id":"2026-11-19-c1","type":"carousel","publish_at":"2026-11-19T12:00:00-06:00","pokemon":"...",
 "design_keys":["<main>","<others...>"],
 "slides":[{"hero":"<main design URL (2000x2000 Cloudinary or Etsy mockup)>"},
           {"video":"https://res.cloudinary.com/rntnboij/video/upload/c_crop,w_720,h_720,x_0,y_185/c_scale,w_1080/q_auto/v1795034320/ig_holo_video.mp4"},
           {"collage":["<design URL 2>","<design URL 3>","... up to 8 other approved designs of the same Pokémon"]},
           {"image":"https://res.cloudinary.com/rntnboij/image/upload/c_scale,w_1080/f_jpg,q_90/ig_more_designs.jpg"}],
 "caption_ig":"...","caption_fb":"..."}
```

## Records
- `catalog/designs.json`: {design_key: {pokemon, listing_id, image, verdict (approved/rejected/needs_check),
  reason, pocket, own, art_check, used: [dates]}}. Mark every design shown (main AND collage) as used.
- `state/status.json`: written by the Action (rendered URLs, IG/FB permalinks, errors).
Report failures to Arturo with a push notification.
