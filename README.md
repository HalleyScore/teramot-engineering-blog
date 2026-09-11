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
`<org>.github.io` (GitHub Pages custom domain). This is not managed in this
repo — set it up in the DNS zone that manages `teramot.com`.
