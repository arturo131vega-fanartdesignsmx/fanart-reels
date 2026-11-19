# Daily planner — FanartDesignsMX Reels & Carousels

Owner: Arturo (FanartDesignsMX, Etsy shop 66814655, IG @fanartdesignsmx, FB Page "Fanart Designs MX").
The GitHub Action `pipeline.yml` renders and publishes whatever is in `queue/`. The planner (a daily
Claude task) only curates designs and writes the queue. Never publish anything by other means.

## Hard rules (from Arturo)
1. **Only designs that do NOT exist as physical printed cards.** TCG Pocket-only or Arturo's own designs
   (often "Illus. Arturo Vega") are fine. Verify every design with the review tool before using it:
   push `review/request.json`, wait for "Real-card review sheets", read `review/out/_summary.json`.
   - `REAL_PRINTED_MATCH` → reject (record in `catalog/designs.json` with the matching card id).
   - The OCR verdict is only a first filter: it MISSES matches (e.g. Lucario d1, Charizard Y d2/d3, Alakazam).
     Always open `<key>_design.jpg`, read the card name, HP and every attack/ability name yourself, and
     search them in `<key>.json` `real_cards` (case-insensitive; `attacks`/`abilities` may contain null).
     If `real_cards` is empty, TCGdex rate-limited: resubmit that key later, never assume "no match".
   - Any printed (non-Pocket) card with the same attack/ability names → reject. Set numbers like
     "ASC 294/217" or an illustrator other than Arturo Vega on the card → reject (copy of a real card).
   - Pocket-only match or no match at all → approve.
2. **Watermark always**: reels get the diagonal "Fanart Designs MX" overlay automatically; carousel
   image slides must use the Cloudinary fetch URL with the text overlay (see template below).
3. **No repeats**: never the same Pokémon twice within 14 days (all formats), never the same design twice.
4. **Pick Pokémon by popularity** using `catalog/popular.json` (weighted random: tier1 5, tier2 3, other 1),
   then find that Pokémon's listings in the shop (Etsy `etsy_get_shop_listings_active` with keywords).
5. Subtitles: approved Mega Mewtwo Y style only (white with black outline, yellow keywords, no box).
6. Every post gets a **new dialogue** and a **new caption** (never reuse text). Max 5 hashtags.
   Keep the offer exact: "Buy 2+ cards, save 25% with code 25OFF". Always include
   "Fan-made art card. Not an official Pokémon / Nintendo product."

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
Script: 12–16 s total, 4 sentences: hook (varied: question, challenge, "this card doesn't exist", etc.),
product (handmade · holographic · real card size, reworded), offer (exact numbers), CTA (link in bio).
Spell numbers in the spoken part and give the display form as [spoken, display].

Carousel:
```
{"id":"2026-11-19-c1","type":"carousel","publish_at":"2026-11-19T12:00:00-06:00","pokemon":"...",
 "slides":[{"image":"https://res.cloudinary.com/rntnboij/image/fetch/c_fill,w_1080,h_1080/l_text:Arial_74_bold:Fanart%20Designs%20MX,co_rgb:FFFFFF,o_38,a_-50/fl_layer_apply,g_center/f_jpg,q_90/<design URL>"},
           {"video":"https://res.cloudinary.com/rntnboij/video/upload/e_accelerate:-50/c_pad,w_1080,h_1080,b_blurred:400:15/q_auto/v1795034320/ig_holo_video.mp4"},
           {"image":"<same overlay>/<listing 'all designs' image or another listing of the same Pokémon>"},
           {"image":"https://res.cloudinary.com/rntnboij/image/upload/c_scale,w_1080/f_jpg,q_90/ig_more_designs.jpg"}],
 "caption_ig":"...","caption_fb":"..."}
```

## Records
- `catalog/designs.json`: {design_key: {pokemon, listing_id, image, verdict, reason, used: [dates]}}
- `state/status.json`: written by the Action (rendered URLs, IG/FB permalinks, errors).
Report failures to Arturo with a push notification.
