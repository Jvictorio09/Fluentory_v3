import json


def build_course_seo_metadata(course, canonical_url="", site_name="Fluentory"):
    """
    Return SEO metadata dictionary for course pages.
    """
    title = f"{course.name} | {site_name}"
    description = (course.short_description or course.description or "").strip()
    if len(description) > 160:
        description = f"{description[:157].rstrip()}..."
    image_url = ""
    if getattr(course, "thumbnail", None):
        try:
            image_url = course.thumbnail.url
        except Exception:
            image_url = ""
    return {
        "title": title,
        "description": description,
        "canonical_url": canonical_url,
        "image_url": image_url,
        "type": "course",
        "site_name": site_name,
    }


def build_course_json_ld(course, canonical_url="", provider_name="Fluentory"):
    """
    Return JSON-LD string (Course + Offer) for search engines.
    """
    data = {
        "@context": "https://schema.org",
        "@type": "Course",
        "name": course.name,
        "description": (course.short_description or course.description or "").strip(),
        "provider": {
            "@type": "Organization",
            "name": provider_name,
        },
        "url": canonical_url,
    }
    if getattr(course, "is_paid", False) and getattr(course, "price", None):
        data["offers"] = {
            "@type": "Offer",
            "price": str(course.price),
            "priceCurrency": getattr(course, "currency", "USD") or "USD",
            "availability": "https://schema.org/InStock",
            "url": canonical_url,
        }
    return json.dumps(data, ensure_ascii=False)
