#!.venv/bin/python

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import markdown  # type: ignore
import requests  # type: ignore
import typer
from dotenv import load_dotenv

from library.env import get_env_var
from library.project import Project
from library.settings import PostType

app = typer.Typer()
load_dotenv()


def get_hubspot_token() -> str:
    """Retrieve HubSpot API token from environment."""
    token = get_env_var("HUBSPOT_API_TOKEN")
    if not token:
        msg = "Error: HUBSPOT_API_TOKEN not found in environment"
        typer.echo(msg)
        raise typer.Exit(code=1)
    return token


def fetch_content_groups(token: str) -> Dict[str, dict]:
    """Fetch all blog tags/categories from HubSpot API."""
    url = "https://api.hubapi.com/cms/v3/blogs/tags"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        typer.echo(f"Fetching blog tags from: {url}")

        # Add query parameters to get all tags
        params = {
            "limit": 100
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        typer.echo("✅ Successfully fetched blog tags")

        # Convert to dict with id as key
        tags = {}
        for tag in data.get("results", []):
            tags[str(tag["id"])] = tag

        return tags

    except requests.exceptions.RequestException as e:
        typer.echo(f"❌ Error fetching blog tags: {e}")
        if hasattr(e, 'response') and e.response is not None:
            typer.echo(f"Response status: {e.response.status_code}")
            typer.echo(f"Response text: {e.response.text}")
        typer.echo("\nPossible issues:")
        typer.echo("   1. Your HubSpot account may not have CMS features")
        typer.echo("   2. The 'content' scope may not be properly configured")
        typer.echo("   3. Your access token may be invalid or expired")
        raise typer.Exit(code=1)


def fetch_blogs(token: str) -> Dict[str, dict]:
    """Fetch all blogs from HubSpot API."""
    url = "https://api.hubapi.com/cms/v3/blogs/posts"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        typer.echo(f"Fetching blogs from: {url}")
        params = {"limit": 1}  # Just get one to check what blogs exist
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        typer.echo("✅ Successfully accessed blogs endpoint")

        # Extract unique blog IDs from posts
        blogs = {}
        for post in data.get("results", []):
            blog_id = str(post.get("contentGroupId", ""))
            if blog_id and blog_id not in blogs:
                blogs[blog_id] = {
                    "id": blog_id,
                    "name": f"Blog {blog_id}"
                }

        return blogs

    except requests.exceptions.RequestException as e:
        typer.echo(f"⚠️  Could not fetch blogs: {e}")
        return {}


def fetch_blog_authors(token: str) -> Dict[str, dict]:
    """Fetch all blog authors from HubSpot API."""
    url = "https://api.hubapi.com/cms/v3/blogs/authors"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        typer.echo(f"Fetching blog authors from: {url}")
        params = {"limit": 100}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        typer.echo("✅ Successfully fetched blog authors")

        # Convert to dict with id as key
        authors = {}
        for author in data.get("results", []):
            authors[str(author["id"])] = author

        return authors

    except requests.exceptions.RequestException as e:
        typer.echo(f"⚠️  Could not fetch blog authors: {e}")
        return {}


def find_author_by_name(
    authors: Dict[str, dict], author_name: str
) -> Optional[str]:
    """Find blog author ID by name."""
    author_lower = author_name.lower().strip()

    for author_id, author_info in authors.items():
        # Check fullName, displayName, or name fields
        full_name = author_info.get("fullName", "").lower().strip()
        display_name = author_info.get("displayName", "").lower().strip()
        name = author_info.get("name", "").lower().strip()

        if (author_lower == full_name or
                author_lower == display_name or
                author_lower == name):
            return author_id

    # Try partial match
    for author_id, author_info in authors.items():
        full_name = author_info.get("fullName", "").lower().strip()
        display_name = author_info.get("displayName", "").lower().strip()
        name = author_info.get("name", "").lower().strip()

        if (author_lower in full_name or
                author_lower in display_name or
                author_lower in name):
            return author_id

    return None


def update_content_groups_file(
    project: Project, token: str
) -> tuple[Dict[str, dict], Dict[str, dict], Dict[str, dict]]:
    """Update tags, blogs, and authors JSON files from HubSpot API.

    Returns: (tags_dict, blogs_dict, authors_dict)
    """
    settings = project.get_settings()
    tags_file = settings.project_base / "hubspot-tags.json"
    blogs_file = settings.project_base / "hubspot-blogs.json"
    authors_file = settings.project_base / "hubspot-authors.json"

    # Fetch latest tags from API
    tags = fetch_content_groups(token)

    # Fetch blogs
    blogs = fetch_blogs(token)

    # Fetch authors
    authors = fetch_blog_authors(token)

    # Write to files
    tags_file.write_text(json.dumps(tags, indent=2))
    typer.echo(f"Updated tags: {len(tags)} tags found")

    if blogs:
        blogs_file.write_text(json.dumps(blogs, indent=2))
        typer.echo(f"Updated blogs: {len(blogs)} blogs found")

    if authors:
        authors_file.write_text(json.dumps(authors, indent=2))
        typer.echo(f"Updated authors: {len(authors)} authors found")

    return tags, blogs, authors


def load_content_groups(project: Project) -> Dict[str, dict]:
    """Load tags from JSON file."""
    settings = project.get_settings()
    tags_file = settings.project_base / "hubspot-tags.json"

    if not tags_file.exists():
        return {}

    return json.loads(tags_file.read_text())


def load_blogs(project: Project) -> Dict[str, dict]:
    """Load blogs from JSON file."""
    settings = project.get_settings()
    blogs_file = settings.project_base / "hubspot-blogs.json"

    if not blogs_file.exists():
        return {}

    return json.loads(blogs_file.read_text())


def load_authors(project: Project) -> Dict[str, dict]:
    """Load authors from JSON file."""
    settings = project.get_settings()
    authors_file = settings.project_base / "hubspot-authors.json"

    if not authors_file.exists():
        return {}

    return json.loads(authors_file.read_text())


def parse_datetime_option(value: str) -> int:
    """Parse ISO datetime string to a UTC timestamp in milliseconds."""
    sanitized = value.strip()
    if sanitized.endswith('Z'):
        sanitized = sanitized[:-1] + '+00:00'

    try:
        dt = datetime.fromisoformat(sanitized)
    except ValueError as exc:
        raise typer.BadParameter(
            "Invalid datetime format. Use ISO 8601, e.g. 2025-10-26T15:00"
        ) from exc

    if dt.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        if local_tz is not None:
            dt = dt.replace(tzinfo=local_tz)
        else:
            dt = dt.replace(tzinfo=timezone.utc)

    dt_utc = dt.astimezone(timezone.utc)
    return int(dt_utc.timestamp() * 1000)


def parse_publish_date_value(value: Any) -> Optional[int]:
    """Normalize HubSpot publish date field to milliseconds."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None

        if stripped.isdigit():
            return int(stripped)

        try:
            iso_value = stripped.replace('Z', '+00:00')
            dt = datetime.fromisoformat(iso_value)
        except ValueError:
            return None

        if dt.tzinfo is None:
            local_tz = datetime.now().astimezone().tzinfo
            if local_tz is not None:
                dt = dt.replace(tzinfo=local_tz)
            else:
                dt = dt.replace(tzinfo=timezone.utc)

        dt_utc = dt.astimezone(timezone.utc)
        return int(dt_utc.timestamp() * 1000)

    return None


def format_local_datetime(timestamp_ms: int) -> str:
    """Format a timestamp (ms) to local time string."""
    dt_local = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt_local.strftime('%Y-%m-%d %H:%M')


def get_latest_publish_date(token: str) -> Optional[int]:
    """Return the furthest scheduled publish date (future) in HubSpot."""
    url = "https://api.hubapi.com/cms/v3/blogs/posts"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    params = {
        "limit": 100,
        "archived": "false"
    }

    latest_future_date: Optional[int] = None
    after: Optional[str] = None
    now_ms = int(datetime.now().timestamp() * 1000)

    while True:
        current_params = dict(params)
        if after:
            current_params["after"] = after

        try:
            response = requests.get(
                url,
                headers=headers,
                params=current_params,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            typer.echo(f"⚠️  Could not inspect existing HubSpot posts: {exc}")
            return None

        data = response.json()
        for post in data.get("results", []):
            state = post.get("state", "").upper()
            if state == "DRAFT":
                continue

            publish_date = (
                parse_publish_date_value(post.get("publishDate")) or
                parse_publish_date_value(post.get("scheduledPublishDate"))
            )

            if publish_date and publish_date >= now_ms:
                if (latest_future_date is None or
                        publish_date > latest_future_date):
                    latest_future_date = publish_date

        paging = data.get("paging", {})
        next_cursor = paging.get("next", {}).get("after")
        if not next_cursor:
            break
        after = next_cursor

    return latest_future_date


def find_content_group_by_name(
    groups: Dict[str, dict], category_name: str
) -> Optional[str]:
    """Find content group ID by matching category name."""
    category_lower = category_name.lower().strip()

    # Try exact match first
    for group_id, group_info in groups.items():
        group_name = group_info.get("name", "").lower().strip()
        if group_name == category_lower:
            return group_id

    # Try match with normalized whitespace and special chars
    # Example: "Habit Formation & Daily Routines"
    #       -> "habit formation daily routines"
    normalized_category = ' '.join(category_lower.replace('&', '').split())

    for group_id, group_info in groups.items():
        group_name = group_info.get("name", "").lower().strip()
        normalized_group = ' '.join(group_name.replace('&', '').split())
        if normalized_group == normalized_category:
            return group_id

    # Try partial match (category contains group name or vice versa)
    for group_id, group_info in groups.items():
        group_name = group_info.get("name", "").lower().strip()
        if category_lower in group_name or group_name in category_lower:
            return group_id

    # Try matching just the first part before "&" or ","
    first_part = category_lower.split('&')[0].split(',')[0].strip()
    if first_part and len(first_part) > 3:  # Avoid matching too short
        for group_id, group_info in groups.items():
            group_name = group_info.get("name", "").lower().strip()
            if first_part in group_name or group_name in first_part:
                return group_id

    return None


def extract_metadata_from_markdown(content: str) -> Dict[str, Any]:
    """Extract metadata from markdown content (first few lines)."""
    lines = content.strip().split('\n')
    metadata: Dict[str, Any] = {
        'category': '',
        'title': '',
        'description': '',
        'image_request': '',
        'keywords': []
    }

    # Extract metadata from first lines (check more lines to be safe)
    for line in lines[:20]:
        line_stripped = line.strip()

        # Handle both formats: "Category:" and "**Category:**"
        if 'category' in line_stripped.lower() and ':' in line_stripped:
            # Extract after the colon
            parts = line_stripped.split(':', 1)
            if len(parts) > 1:
                cat = parts[1].strip().strip('*').strip()
                metadata['category'] = cat

        elif ('title' in line_stripped.lower() and
              ':' in line_stripped and
              'meta' not in line_stripped.lower()):
            parts = line_stripped.split(':', 1)
            if len(parts) > 1:
                title = parts[1].strip().strip('*').strip()
                metadata['title'] = title

        elif ('description' in line_stripped.lower() and
              ':' in line_stripped):
            parts = line_stripped.split(':', 1)
            if len(parts) > 1:
                desc = parts[1].strip().strip('*').strip()
                metadata['description'] = desc

        elif ('image request' in line_stripped.lower() and
              ':' in line_stripped):
            parts = line_stripped.split(':', 1)
            if len(parts) > 1:
                img = parts[1].strip().strip('*').strip()
                metadata['image_request'] = img

    # Extract keywords from end of file
    for line in reversed(lines):
        line_stripped = line.strip()
        if (line_stripped.startswith('`') and
                line_stripped.endswith('`')):
            # Remove backticks and split by comma
            keywords_str = line_stripped.strip('`')
            keywords_list = [
                k.strip().strip('`').strip()
                for k in keywords_str.split(',')
                if k.strip()
            ]
            metadata['keywords'] = keywords_list
            break
        # Check for hashtag format (#TimeManagement #ProductivityTips)
        elif line_stripped.startswith('#') and ' #' in line_stripped:
            # Extract hashtags
            hashtags = re.findall(r'#(\w+)', line_stripped)
            if hashtags:
                metadata['keywords'] = hashtags
                break

    return metadata


def get_post_body_from_markdown(content: str) -> str:
    """Extract the main post body from markdown, removing metadata."""
    lines = content.strip().split('\n')

    # Skip metadata lines at the beginning
    start_idx = 0
    for i, line in enumerate(lines):
        # Look for the first H1 heading (main title)
        if (line.strip().startswith('#') and
                not line.strip().startswith('##')):
            # Found the first main heading
            start_idx = i
            break
        # If we find text that looks like metadata, keep skipping
        if (i < 20 and
            (':' in line or
             line.strip().startswith('**') or
             line.lower().startswith('style') or
             line.lower().startswith('category') or
             line.lower().startswith('title') or
             line.lower().startswith('description') or
             line.lower().startswith('image request'))):
            continue
        # If we've gone past 20 lines without finding H1
        if i >= 20:
            start_idx = 0
            break

    # Remove keywords and hashtags from end
    end_idx = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        line_stripped = lines[i].strip()
        if ((line_stripped.startswith('`') and
             line_stripped.endswith('`')) or
            (line_stripped.startswith('#') and
             ' #' in line_stripped)):
            end_idx = i
            break
        # Also check for "---" separator near the end
        if line_stripped == '---' and i > len(lines) - 10:
            end_idx = i
            break

    # Get the body content
    body_lines = lines[start_idx:end_idx]

    # Remove standalone "---" separators
    body_lines = [line for line in body_lines if line.strip() != '---']

    # Remove "Call to Action" section and everything after it
    filtered_lines = []
    skip_rest = False

    for line in body_lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()

        # Check for "Call to Action" (various formats)
        # - As a heading: ## Call to Action
        # - As bold: **Call to Action**
        # - As plain text: Call to Action (standalone line)
        is_cta = False
        if 'call to action' in line_lower or 'call-to-action' in line_lower:
            # Check if it's a heading, bold, or standalone
            if (line.startswith('#') or
                    line.startswith('**') or
                    line_stripped == 'Call to Action' or
                    line_stripped == 'Call-to-Action'):
                is_cta = True

        if is_cta:
            skip_rest = True
            continue

        if not skip_rest:
            filtered_lines.append(line)

    return '\n'.join(filtered_lines).strip()


def replace_placeholders(content: str, as_html: bool = False) -> str:
    """Replace placeholders like {url} with actual values.

    Args:
        content: The content to process
        as_html: If True, create HTML links; if False, use markdown links
    """
    # Get URL from environment or use default
    app_url = get_env_var(
        "APP_URL",
        "https://smarter.day/download"
    )

    # Replace {url} placeholder with appropriate link format
    if as_html:
        # Create HTML link for already-converted HTML content
        link = f'<a href="{app_url}" target="_blank">Smarter.Day</a>'
    else:
        # Create markdown link for markdown content
        link = f'[Smarter.Day]({app_url})'

    content = content.replace('{url}', link)

    return content


def markdown_to_html(markdown_content: str) -> str:
    """Convert markdown to HTML."""
    # Configure markdown with extensions
    md = markdown.Markdown(
        extensions=['extra', 'nl2br', 'sane_lists']
    )
    html = md.convert(markdown_content)

    # Replace placeholders AFTER converting to HTML
    # This allows us to insert proper HTML links
    html = replace_placeholders(html, as_html=True)

    return html


def find_blog_post_files(
    title: str, project: Project
) -> tuple[Optional[Path], Optional[Path]]:
    """Find the humanized and original blog post files.

    Priority: .reviewed.md > .humanized.md > .md
    Returns: (humanized_file, original_file)
    """
    settings = project.get_settings()
    blog_dir = settings.post_dirs[PostType.BLOG]

    title_dir = blog_dir / title

    if not title_dir.exists():
        return None, None

    # Find all files matching patterns
    # Priority: reviewed > humanized > original
    reviewed_pattern = re.compile(
        r'^result_(\d+)\.([a-z]{2})\.humanized\.reviewed\.md$'
    )
    humanized_pattern = re.compile(
        r'^result_(\d+)\.([a-z]{2})\.humanized\.md$'
    )
    original_pattern = re.compile(r'^result_(\d+)\.([a-z]{2})\.md$')

    reviewed_candidates = []
    humanized_candidates = []
    original_candidates = []

    for file in title_dir.iterdir():
        reviewed_match = reviewed_pattern.match(file.name)
        humanized_match = humanized_pattern.match(file.name)
        original_match = original_pattern.match(file.name)

        if reviewed_match:
            version_num = int(reviewed_match.group(1))
            lang_code = reviewed_match.group(2)
            reviewed_candidates.append((version_num, lang_code, file))
        elif humanized_match:
            version_num = int(humanized_match.group(1))
            lang_code = humanized_match.group(2)
            humanized_candidates.append((version_num, lang_code, file))
        elif original_match:
            version_num = int(original_match.group(1))
            lang_code = original_match.group(2)
            original_candidates.append((version_num, lang_code, file))

    # Prioritize: reviewed > humanized > original
    # Use reviewed if available, otherwise humanized, otherwise nothing
    if reviewed_candidates:
        content_candidates = reviewed_candidates
    elif humanized_candidates:
        content_candidates = humanized_candidates
    else:
        return None, None

    # Sort by version number (descending) to get the latest
    content_candidates.sort(key=lambda x: x[0], reverse=True)
    original_candidates.sort(key=lambda x: x[0], reverse=True)

    # Get latest version
    latest_version = content_candidates[0][0]

    # Filter to only latest version
    latest_content = [
        c for c in content_candidates if c[0] == latest_version
    ]
    latest_original = [
        c for c in original_candidates if c[0] == latest_version
    ]

    # Prefer English (en) if available
    content_file = None
    original_file = None

    for version, lang, file in latest_content:
        if lang == 'en':
            content_file = file
            break

    if not content_file and latest_content:
        content_file = latest_content[0][2]

    for version, lang, file in latest_original:
        if lang == 'en':
            original_file = file
            break

    if not original_file and latest_original:
        original_file = latest_original[0][2]

    return content_file, original_file


def load_published_posts(project: Project) -> List[str]:
    """Load list of already published post titles."""
    settings = project.get_settings()
    posts_file = settings.project_base / "hubspot-posts.txt"

    if not posts_file.exists():
        return []

    content = posts_file.read_text().splitlines()
    return [
        line.strip() for line in content
        if line.strip() and not line.strip().startswith('#')
    ]


def save_published_post(project: Project, title: str):
    """Add title to the published posts file."""
    settings = project.get_settings()
    posts_file = settings.project_base / "hubspot-posts.txt"

    # Read existing posts
    existing = load_published_posts(project)

    # Add new title if not already there
    if title not in existing:
        existing.append(title)

    # Write back
    posts_file.write_text('\n'.join(existing) + '\n')


def sanitize_title(title: str) -> str:
    """Sanitize blog title to remove problematic characters.

    Keeps only: alphanumeric, spaces, hyphens, and apostrophes
    Removes: quotes, special characters, etc.
    """
    # Replace common problematic characters
    title = title.replace('"', '')  # Remove double quotes
    title = title.replace('"', '')  # Remove smart quotes (opening)
    title = title.replace('"', '')  # Remove smart quotes (closing)
    title = title.replace('`', '')  # Remove backticks
    title = title.replace('´', '')  # Remove acute accent
    title = title.replace(''', "'")  # Replace smart apostrophe with regular
    title = title.replace(''', "'")  # Replace smart apostrophe with regular

    # Keep only: alphanumeric, spaces, hyphens, apostrophes, basic punctuation
    # Allow: a-z, A-Z, 0-9, space, hyphen, apostrophe, colon, ?, !, &
    sanitized = re.sub(r'[^a-zA-Z0-9\s\-\':\?!&]', '', title)

    # Clean up multiple spaces
    sanitized = re.sub(r'\s+', ' ', sanitized)

    # Trim whitespace
    sanitized = sanitized.strip()

    return sanitized


def create_blog_post(
    token: str,
    title: str,
    content_group_id: str,
    slug: str,
    post_body: str,
    meta_description: str,
    keywords: List[str],
    tag_ids: Optional[List[str]] = None,
    blog_author_id: Optional[str] = None,
    publish_date: Optional[int] = None,
    featured_image_url: Optional[str] = None
) -> dict:
    """Create a blog post in HubSpot.

    Args:
        publish_date: Unix timestamp in milliseconds for publish date
        featured_image_url: URL of the featured image for the post
    """
    url = "https://api.hubapi.com/cms/v3/blogs/posts"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create slug from title
    if not slug:
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

    # Limit description to 155 chars
    desc = meta_description[:155] if meta_description else ""

    now_ms = int(datetime.now().timestamp() * 1000)
    is_future_publish = bool(publish_date and publish_date > now_ms)

    payload = {
        "name": title,
        "contentGroupId": content_group_id,
        "slug": slug,
        "postBody": post_body,
        "metaDescription": desc,
        "useFeaturedImage": bool(featured_image_url)
    }

    # Add blog author if provided
    if blog_author_id:
        payload["blogAuthorId"] = blog_author_id

    # Add tag IDs (categories) if provided
    if tag_ids:
        payload["tagIds"] = tag_ids

    # Set publish state and timing
    if is_future_publish:
        payload["state"] = "SCHEDULED"
        # Use publishDate for scheduling; also send scheduledPublishDate
        payload["publishDate"] = publish_date
        payload["scheduledPublishDate"] = publish_date
    else:
        payload["state"] = "PUBLISHED"
        if publish_date:
            payload["publishDate"] = publish_date

    # Add featured image if provided
    if featured_image_url:
        payload["featuredImage"] = featured_image_url
        payload["featuredImageAltText"] = title  # Use title as alt text

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        typer.echo(f"Error creating blog post: {e}")
        if hasattr(e, 'response') and e.response is not None:
            typer.echo(f"Response: {e.response.text}")
        raise


@app.command()
def publish(
    project_id: str = typer.Argument(..., help="Project identifier"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview without actually posting"
    ),
    limit: int = typer.Option(
        0,
        "--limit",
        help="Limit number of posts (0 = no limit)"
    ),
    start_datetime: Optional[str] = typer.Option(
        None,
        "--start-datetime",
        help="ISO datetime to start scheduling from (local timezone if no TZ)"
    ),
    continue_by_scheduled: bool = typer.Option(
        True,
        "--continue-by-scheduled",
        help=(
            "Continue schedule after the furthest future post already in "
            "HubSpot"
        )
    )
):
    """
    Publish blog posts from markdown files to HubSpot.
    """

    # Load project
    project = Project(project_id)
    settings = project.get_settings()

    # For dry run, we can work without API token
    if not dry_run:
        # Get HubSpot token
        token = get_hubspot_token()

        # Update tags, blogs, and authors from HubSpot API (once at start)
        typer.echo("Fetching tags, blogs, and authors from HubSpot...")
        tags, blogs, authors = update_content_groups_file(project, token)
    else:
        # Try to load from cache or use empty dict
        token = ""
        tags = load_content_groups(project)
        blogs = load_blogs(project)
        authors = load_authors(project)

        if not tags:
            typer.echo("⚠️  No cached tags found")
            typer.echo("   Using mock tags for dry run")
            tags = {
                "mock-tag-id": {
                    "id": "mock-tag-id",
                    "name": "Productivity",
                    "slug": "productivity"
                }
            }

        if not blogs:
            typer.echo("⚠️  No cached blogs found")
            typer.echo("   Using mock blog for dry run")
            blogs = {
                "mock-blog-id": {
                    "id": "mock-blog-id",
                    "name": "Default Blog"
                }
            }

    typer.echo("\nAvailable tags (categories):")
    for tid, tag_info in tags.items():
        tag_name = tag_info.get('name')
        typer.echo(f"  - {tag_name} (ID: {tid})")

    typer.echo("\nAvailable blogs:")
    for bid, blog_info in blogs.items():
        blog_name = blog_info.get('name')
        typer.echo(f"  - {blog_name} (ID: {bid})")

    # Load already published posts
    published_posts = load_published_posts(project)
    typer.echo(f"Already published: {len(published_posts)} posts")

    # Read titles from titles.txt
    if not settings.titles_file.exists():
        typer.echo(f"Titles file not found: {settings.titles_file}")
        raise typer.Exit(code=1)

    titles = settings.titles_file.read_text().splitlines()

    # Filter out commented and empty lines
    active_titles = [
        title.strip() for title in titles
        if title.strip() and not title.strip().startswith('#')
    ]

    typer.echo(f"Found {len(active_titles)} active titles")

    # Get default featured image URL from environment (optional)
    featured_image_url = get_env_var("HUBSPOT_FEATURED_IMAGE_URL", "")
    if featured_image_url:
        typer.echo(f"📷 Using featured image: {featured_image_url}")
    else:
        typer.echo("ℹ️  No default featured image set")

    # Find blog author "Dmitri Meshin"
    blog_author_id = None
    if authors:
        blog_author_id = find_author_by_name(authors, "Dmitri Meshin")
        if blog_author_id:
            author_name = authors[blog_author_id].get(
                'fullName', 'Dmitri Meshin'
            )
            typer.echo(
                f"✅ Found blog author: {author_name} (ID: {blog_author_id})"
            )
        else:
            typer.echo("⚠️  Author 'Dmitri Meshin' not found in HubSpot")
            typer.echo("   Available authors:")
            for aid, ainfo in list(authors.items())[:5]:
                aname = ainfo.get('fullName', ainfo.get('name', aid))
                typer.echo(f"     - {aname}")

    # Track publishing stats
    published_count = 0
    skipped_count = 0
    error_count = 0

    # Get publish interval from environment (in hours), default to 3 hours
    interval_hours = float(
        get_env_var("HUBSPOT_PUBLISH_INTERVAL_HOURS", "3")
    )
    interval_ms = int(interval_hours * 60 * 60 * 1000)

    typer.echo(f"📅 Post interval: {interval_hours} hours between posts")

    now_ms = int(datetime.now().timestamp() * 1000)
    base_publish_time = now_ms
    start_timestamp_ms: Optional[int] = None

    if start_datetime:
        start_timestamp_ms = parse_datetime_option(start_datetime)
        if start_timestamp_ms < now_ms:
            typer.echo(
                "⚠️  Provided start datetime is in the past. Using current "
                "time instead."
            )
            start_timestamp_ms = now_ms

        base_publish_time = start_timestamp_ms
        typer.echo(
            f"📌 Start date: {format_local_datetime(base_publish_time)}"
        )

    if continue_by_scheduled:
        if dry_run and not token:
            typer.echo(
                "⚠️  Cannot continue schedule without HubSpot token in dry "
                "run. Using start time or now + interval."
            )
            if start_timestamp_ms is not None:
                base_publish_time = start_timestamp_ms
            else:
                base_publish_time = now_ms + interval_ms
                typer.echo(
                    "ℹ️  Falling back to now + interval for dry run: "
                    f"{format_local_datetime(base_publish_time)}"
                )
        else:
            typer.echo("🔁 Inspecting HubSpot for future scheduled posts...")
            latest_future_date = get_latest_publish_date(token)

            if latest_future_date is not None:
                candidate_base = latest_future_date + interval_ms
                if (start_timestamp_ms is not None and
                        start_timestamp_ms > candidate_base):
                    candidate_base = start_timestamp_ms
                if candidate_base < now_ms:
                    candidate_base = now_ms
                base_publish_time = candidate_base
                typer.echo(
                    f"🔁 Last scheduled post: "
                    f"{format_local_datetime(latest_future_date)}"
                )
                typer.echo(
                    f"🔁 Next slot begins: "
                    f"{format_local_datetime(base_publish_time)}"
                )
            else:
                candidate_base = now_ms + interval_ms
                if (start_timestamp_ms is not None and
                        start_timestamp_ms > candidate_base):
                    candidate_base = start_timestamp_ms
                base_publish_time = candidate_base
                typer.echo(
                    "ℹ️  No future scheduled posts found. Starting at "
                    f"{format_local_datetime(base_publish_time)}"
                )

    if start_timestamp_ms is None and not continue_by_scheduled:
        typer.echo(
            f"🕒 First post scheduled for: "
            f"{format_local_datetime(base_publish_time)}"
        )

    for title in active_titles:
        # Check if already published
        if title in published_posts:
            typer.echo(f"⏭️  Skipping (already published): {title}")
            skipped_count += 1
            continue

        # Find the markdown files (content and original)
        # Priority: .reviewed.md > .humanized.md
        content_file, original_file = find_blog_post_files(
            title, project
        )

        if not content_file:
            typer.echo(f"⚠️  No markdown file found for: {title}")
            skipped_count += 1
            continue

        typer.echo(f"\n📝 Processing: {title}")
        rel_path = content_file.relative_to(settings.project_base)
        typer.echo(f"   File: {rel_path}")

        # Read markdown content from content file (reviewed or humanized)
        content = content_file.read_text()

        # Extract metadata from original file if available
        if original_file and original_file.exists():
            original_content = original_file.read_text()
            metadata = extract_metadata_from_markdown(original_content)
        else:
            # Fallback to content file
            metadata = extract_metadata_from_markdown(content)

        # Get post body from content file (reviewed or humanized)
        post_body_md = get_post_body_from_markdown(content)

        # Convert markdown to HTML
        post_body_html = markdown_to_html(post_body_md)

        # Find blog (content group) - use first available blog
        blog_id: Optional[str] = None
        if blogs:
            blog_id = list(blogs.keys())[0]

        if not blog_id:
            typer.echo("   ❌ No blogs available in HubSpot")
            error_count += 1
            continue

        # Find tag ID by category name
        category = metadata.get('category', '')
        tag_ids: List[str] = []

        if category:
            typer.echo(f"   🔍 Looking for tag matching: '{category}'")
            tag_id: Optional[str] = find_content_group_by_name(
                tags, str(category)
            )
            if tag_id:
                tag_ids = [tag_id]
                # Show which tag was matched
                matched_tag_name = tags[tag_id].get('name', tag_id)
                msg = f"   ✅ Matched to tag: '{matched_tag_name}'"
                typer.echo(msg)
            else:
                msg = (f"   ⚠️  No matching tag found for "
                       f"category '{category}'")
                typer.echo(msg)
                # Show available tags for debugging
                typer.echo("   Available tags:")
                for tid, tinfo in list(tags.items())[:5]:
                    typer.echo(f"     - {tinfo.get('name', tid)}")

        post_title_raw = metadata.get('title') or title
        description = metadata.get('description', '')
        keywords_data = metadata.get('keywords', [])

        # Sanitize the title to remove problematic characters
        post_title = sanitize_title(str(post_title_raw))

        # Ensure description is not empty (HubSpot requires it)
        if not description or not str(description).strip():
            # Use first 155 chars of content as fallback
            description = post_title[:155]

        # Ensure keywords is a list
        if isinstance(keywords_data, str):
            keywords_list: List[str] = [keywords_data]
        else:
            keywords_list = list(keywords_data)

        # Calculate publish date, spacing each post by the chosen interval
        time_offset = published_count * interval_ms
        publish_date_ms = base_publish_time + time_offset
        publish_date_str = format_local_datetime(publish_date_ms)

        typer.echo(f"   Title: {post_title}")
        typer.echo(f"   Category: {category}")
        typer.echo(f"   Blog ID: {blog_id}")
        typer.echo(f"   Tag IDs: {tag_ids}")
        typer.echo(f"   Author ID: {blog_author_id}")
        typer.echo(f"   Publish Date: {publish_date_str}")
        typer.echo(f"   Description: {str(description)[:100]}...")
        typer.echo(f"   Keywords: {', '.join(keywords_list[:5])}")

        if dry_run:
            typer.echo("   🔍 DRY RUN - Would publish to HubSpot")
            published_count += 1
        else:
            try:
                # Create the blog post
                result = create_blog_post(
                    token=token,
                    title=post_title,
                    content_group_id=blog_id,
                    slug="",  # Let HubSpot generate from title
                    post_body=post_body_html,
                    meta_description=str(description),
                    keywords=keywords_list,
                    tag_ids=tag_ids,
                    blog_author_id=blog_author_id,
                    publish_date=publish_date_ms,
                    featured_image_url=featured_image_url or None
                )

                post_id = result.get('id')
                typer.echo(
                    f"   ✅ Published successfully! Post ID: {post_id}"
                )

                # Save to published posts file
                save_published_post(project, title)
                published_count += 1

            except Exception as e:
                typer.echo(f"   ❌ Error publishing: {e}")

                # Save to published posts file even on error
                # This prevents retrying posts that failed due to
                # data issues (missing metadata, etc.)
                save_published_post(project, title)
                error_count += 1

        # Check limit
        if limit > 0 and published_count >= limit:
            typer.echo(f"\nReached publish limit of {limit} posts")
            break

    # Summary
    separator = "=" * 60
    typer.echo(f"\n{separator}")
    typer.echo("Publishing Summary:")
    typer.echo(f"  Published: {published_count}")
    typer.echo(f"  Skipped: {skipped_count}")
    typer.echo(f"  Errors: {error_count}")
    typer.echo(separator)


@app.command()
def list_groups(
    project_id: str = typer.Argument(..., help="Project identifier")
):
    """
    List available HubSpot content groups.
    """
    # Load project to get settings
    Project(project_id)
    token = get_hubspot_token()

    typer.echo("Fetching content groups from HubSpot...")
    groups = fetch_content_groups(token)

    typer.echo(f"\nFound {len(groups)} content groups:\n")
    for group_id, group_info in groups.items():
        typer.echo(f"ID: {group_id}")
        typer.echo(f"  Name: {group_info.get('name')}")
        typer.echo(f"  Slug: {group_info.get('slug')}")
        typer.echo(f"  Language: {group_info.get('language', 'N/A')}")
        typer.echo()


if __name__ == "__main__":
    app()
