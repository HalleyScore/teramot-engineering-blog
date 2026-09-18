# Teramot Engineering Blog

Engineering blog for Teramot, built with [Hugo](https://gohugo.io/) and the
[Blowfish](https://blowfish.page/) theme. Deploys to
[engineering.teramot.com](https://engineering.teramot.com) via GitHub Pages.

## Local development

```sh
git clone --recurse-submodules <repo-url>
cd teramot-engineering-blog
hugo server
```

Site is served at http://localhost:1313/.

### Prerequisites

Hugo (extended) plus `asciidoctor` and `rouge`, which Hugo shells out to for
`.adoc` content — not optional if any post uses AsciiDoc, because a missing
binary fails the build rather than degrading:

```sh
sudo pacman -S hugo asciidoctor ruby-rouge      # Arch
sudo apt install hugo asciidoctor ruby-rouge    # Debian/Ubuntu
```

Rouge can also be installed per-user, without root, if you already have Ruby:

```sh
gem install --user-install rouge
```

## Writing a post

Markdown and AsciiDoc are both supported; pick per post by extension.

```sh
hugo new content posts/my-post-slug/index.md    # Markdown (Goldmark)
hugo new content posts/my-post-slug/index.adoc  # AsciiDoc (Asciidoctor)
```

Edit the front matter and content, then set `draft: false` to publish. Posts
live under `content/posts/`.

### AsciiDoc notes

Rendering is configured in `config/_default/markup.toml` (`[asciidocExt]`), and
`asciidoctor` is allowed to run in `config/_default/security.toml` — Hugo
refuses to exec binaries that are not on that allowlist, and the list replaces
Hugo's defaults rather than extending them, so it must be kept in sync when
Hugo is upgraded.

- Front matter is still Hugo's (`---` YAML), not an AsciiDoc document header.
  Do not add a `= Title` line; the `title` key already renders one.
- Heading IDs are configured to match Goldmark's (`#my-heading`), so anchors
  behave the same across both formats.
- Shortcodes (`{{< chart >}}`, `{{< intro >}}`, …) work. Hugo substitutes them
  after Asciidoctor has run, so the HTML they emit is never re-parsed and
  blank lines inside a shortcode body are safe. Asciidoctor does however wrap
  a block-level shortcode in its own `<div class="paragraph">`, which adds a
  stray margin; wrap the call in a passthrough block for markup identical to
  the Markdown posts:

  ```
  ++++
  {{< chart >}}
  ...
  {{< /chart >}}
  ++++
  ```
- Code blocks are highlighted by Asciidoctor's Rouge rather than Hugo's
  Chroma, but they are styled to be indistinguishable: Rouge emits the same
  Pygments token classes, and `assets/css/custom.css` re-points the theme's
  own Chroma palettes at Rouge's wrapper for both light and dark mode. That
  file is generated — after upgrading the Blowfish submodule, re-run:

  ```sh
  python3 scripts/gen-rouge-css.py
  ```

  `layouts/partials/extend-footer.html` wraps AsciiDoc code blocks in the
  theme's `.highlight-wrapper` so they also pick up its rounding, shadow,
  title bar and copy button, which otherwise only reach Markdown via the
  `render-codeblock.html` hook.

## Deploy

Pushing to `main` triggers `.github/workflows/hugo.yml`, which builds the site
and publishes it via GitHub Pages.

## DNS

`engineering.teramot.com` needs a `CNAME` record pointing at
`halleyscore.github.io` (GitHub Pages custom domain). This is not managed in
this repo — set it up in the DNS zone that manages `teramot.com`.

Note: with `build_type: workflow` (Actions-based Pages deploy, what this repo
uses), GitHub does **not** auto-detect the custom domain from `static/CNAME`
the way it does with branch-based Pages. The domain must also be registered
explicitly on the repo's Pages config:

```sh
gh api -X PUT repos/HalleyScore/teramot-engineering-blog/pages -f "cname=engineering.teramot.com"
gh api -X PUT repos/HalleyScore/teramot-engineering-blog/pages -F "https_enforced=true"
```

(or via Settings → Pages → Custom domain in the GitHub UI). This only needs to
be done once per repo lifetime — it doesn't reset on redeploys.
