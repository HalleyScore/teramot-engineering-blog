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

## Writing a post

```sh
hugo new content posts/my-post-slug/index.md
```

Edit the front matter and content, then set `draft: false` to publish. Posts
live under `content/posts/`.

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
