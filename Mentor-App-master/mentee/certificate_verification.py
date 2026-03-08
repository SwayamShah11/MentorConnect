import ipaddress
import os
import re
import socket
from urllib.parse import urlparse

import requests
from django.utils import timezone

try:
    import cv2
except Exception:
    cv2 = None

try:
    import pypdfium2 as pdfium
except Exception:
    pdfium = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _tokens(text: str):
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2]


def _token_match_ratio(source_text: str, expected_text: str) -> float:
    expected = _tokens(expected_text)
    if not expected:
        return 0.0
    source_set = set(_tokens(source_text))
    matched = sum(1 for t in expected if t in source_set)
    return matched / max(len(expected), 1)


def _is_certificate_like_page(page_text: str):
    text = _normalize(page_text)
    if not text:
        return False, []

    anchor_terms = ("certificate", "credential", "certification")
    support_terms = (
        "verify",
        "verification",
        "completed",
        "completion",
        "issued",
        "recipient",
        "student",
        "learner",
        "authentic",
        "course",
    )
    anchors = [term for term in anchor_terms if term in text]
    supports = [term for term in support_terms if term in text]
    looks_like = bool(anchors) and len(supports) >= 1
    markers = anchors + supports
    return looks_like, markers


def _extract_pdf_text(file_path: str) -> str:
    if not PdfReader:
        return ""
    try:
        reader = PdfReader(file_path)
    except Exception:
        return ""

    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts)


def _extract_qr_payloads_from_pdf(file_path: str, max_pages: int = 3):
    if not cv2 or not pdfium:
        return [], "QR scanner dependencies are unavailable"

    payloads = []
    detector = cv2.QRCodeDetector()

    try:
        doc = pdfium.PdfDocument(file_path)
    except Exception as exc:
        return [], f"Unable to open PDF for QR scan: {exc}"

    try:
        total_pages = min(len(doc), max_pages)
        for page_index in range(total_pages):
            page = doc[page_index]
            bmp = page.render(scale=2)
            img = bmp.to_numpy()
            if img is None:
                continue

            if len(img.shape) == 3 and img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)

            try:
                ok, infos, _, _ = detector.detectAndDecodeMulti(img)
                if ok and infos:
                    for info in infos:
                        if info and info.strip():
                            payloads.append(info.strip())
            except Exception:
                pass

            try:
                single_info, _, _ = detector.detectAndDecode(img)
                if single_info and single_info.strip():
                    payloads.append(single_info.strip())
            except Exception:
                pass
    finally:
        doc.close()

    unique = []
    seen = set()
    for p in payloads:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return unique, ""


def _is_safe_public_url(url: str):
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    if parsed.scheme not in ("http", "https"):
        return False, "Unsupported URL scheme"

    host = (parsed.hostname or "").strip()
    if not host:
        return False, "URL hostname missing"

    if host in ("localhost", "127.0.0.1"):
        return False, "Localhost URLs are blocked"

    try:
        ip_str = socket.gethostbyname(host)
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, "Private/reserved target blocked"
    except Exception:
        return False, "Hostname resolution failed"

    return True, ""


def _validate_qr_payload(payload: str, expected_name: str, expected_title: str, expected_authority: str):
    payload_text = _normalize(payload)

    if payload_text.startswith("http://") or payload_text.startswith("https://"):
        safe, reason = _is_safe_public_url(payload)
        if not safe:
            return False, True, False, reason, {}

        try:
            response = requests.get(payload, timeout=8, allow_redirects=True)
        except Exception as exc:
            return False, True, False, f"QR URL request failed: {exc}", {}

        if response.status_code >= 400:
            return False, True, False, f"QR URL returned HTTP {response.status_code}", {}

        page_text = _normalize(response.text[:300000])
        name_ratio = _token_match_ratio(page_text, expected_name)
        title_ratio = _token_match_ratio(page_text, expected_title)
        authority_ratio = _token_match_ratio(page_text, expected_authority)

        has_name = bool(_tokens(expected_name))
        has_title = bool(_tokens(expected_title))
        has_authority = bool(_tokens(expected_authority))

        strict_name_ok = name_ratio >= 0.45 if has_name else False
        strict_title_ok = title_ratio >= 0.45 if has_title else True
        strict_authority_ok = authority_ratio >= 0.45 if has_authority else True
        strict_match = strict_name_ok or (strict_title_ok and strict_authority_ok)

        relaxed_name_ok = name_ratio >= 0.30 if has_name else True
        relaxed_title_ok = title_ratio >= 0.20 if has_title else True
        relaxed_authority_ok = authority_ratio >= 0.25 if has_authority else True
        relaxed_match = (
            (relaxed_name_ok and (relaxed_title_ok or relaxed_authority_ok))
            if has_name
            else (relaxed_title_ok and relaxed_authority_ok)
        )

        page_valid, markers = _is_certificate_like_page(page_text)
        final_url = response.url or payload
        path = (urlparse(final_url).path or "").lower()
        path_certificate_hint = any(term in path for term in ("certificate", "cert", "credential", "verify"))
        certificate_page_valid = page_valid or path_certificate_hint

        looks_valid = strict_match or (certificate_page_valid and relaxed_match)
        note = (
            f"QR URL reachable; page_valid={certificate_page_valid}; "
            f"name={name_ratio:.2f}, title={title_ratio:.2f}, authority={authority_ratio:.2f}"
        )
        if looks_valid:
            note += "; metadata matched (strict/relaxed)"
        else:
            note += "; metadata mismatch"

        evidence = {
            "certificate_page_valid": certificate_page_valid,
            "strict_match": strict_match,
            "relaxed_match": relaxed_match,
            "name_ratio": name_ratio,
            "title_ratio": title_ratio,
            "authority_ratio": authority_ratio,
            "page_markers": markers[:6],
        }
        return looks_valid, True, True, note, evidence

    name_ratio = _token_match_ratio(payload_text, expected_name)
    title_ratio = _token_match_ratio(payload_text, expected_title)
    authority_ratio = _token_match_ratio(payload_text, expected_authority)
    looks_valid = name_ratio >= 0.6 or (title_ratio >= 0.5 and authority_ratio >= 0.5)
    evidence = {
        "certificate_page_valid": False,
        "strict_match": looks_valid,
        "relaxed_match": looks_valid,
        "name_ratio": name_ratio,
        "title_ratio": title_ratio,
        "authority_ratio": authority_ratio,
        "page_markers": [],
    }
    return looks_valid, False, False, "QR payload parsed", evidence


def _extract_urls_from_text(text: str):
    return re.findall(r"https?://[^\s)\]>]+", text or "", flags=re.IGNORECASE)


def verify_course_certificate(course):
    result = {
        "verification_status": "unverified",
        "verification_notes": "",
        "verification_checked_at": timezone.now(),
        "qr_detected": False,
        "qr_payload": "",
        "qr_url_checked": False,
        "qr_url_accessible": False,
    }

    if not course.certificate:
        result["verification_notes"] = "No certificate file uploaded"
        return result

    try:
        file_path = course.certificate.path
    except Exception as exc:
        result["verification_notes"] = f"Could not resolve certificate path: {exc}"
        return result

    if not file_path or not os.path.exists(file_path):
        result["verification_notes"] = "Certificate file is missing on server"
        return result

    full_text = _normalize(_extract_pdf_text(file_path))
    expected_name = ""
    profile_name = ""
    if course.user:
        try:
            profile_name = (course.user.profile.student_name or "").strip()
        except Exception:
            profile_name = ""
        expected_name = profile_name or (course.user.username or "")

    title = (course.title or "").strip()
    authority = (course.certifying_authority or "").strip()

    name_ratio = _token_match_ratio(full_text, expected_name)
    title_ratio = _token_match_ratio(full_text, title)
    authority_ratio = _token_match_ratio(full_text, authority)

    qr_payloads, qr_error = _extract_qr_payloads_from_pdf(file_path)

    if not qr_payloads:
        fallback_urls = _extract_urls_from_text(full_text)
        if fallback_urls:
            qr_payloads = list(dict.fromkeys(fallback_urls[:5]))
            if qr_error:
                qr_error += " | "
            qr_error += "QR image not decoded; using verification URL detected from certificate text"

    result["qr_detected"] = bool(qr_payloads)
    if qr_payloads:
        result["qr_payload"] = "\n".join(qr_payloads[:5])

    notes = []
    qr_valid = False
    qr_page_valid = False
    qr_relaxed_match = False

    if qr_error:
        notes.append(qr_error)

    if qr_payloads:
        for payload in qr_payloads[:3]:
            is_valid, url_checked, url_accessible, reason, evidence = _validate_qr_payload(
                payload,
                expected_name,
                title,
                authority,
            )
            if url_checked:
                result["qr_url_checked"] = True
            if url_accessible:
                result["qr_url_accessible"] = True
            notes.append(reason)
            if is_valid:
                qr_valid = True
                qr_page_valid = bool(evidence.get("certificate_page_valid"))
                qr_relaxed_match = bool(evidence.get("relaxed_match"))
                page_markers = evidence.get("page_markers", [])
                if page_markers:
                    notes.append(f"Page markers: {', '.join(page_markers)}")
                break
    else:
        notes.append("No QR code detected in first pages of certificate")

    name_required = bool(profile_name)
    name_ok = name_ratio >= 0.45
    title_ok = title_ratio >= 0.45 if title else True
    authority_ok = authority_ratio >= 0.45 if authority else True

    strict_doc_match = title_ok and authority_ok and (name_ok or not name_required)
    qr_page_relaxed_match = qr_valid and result["qr_url_accessible"] and qr_page_valid and qr_relaxed_match

    if qr_valid and (strict_doc_match or qr_page_relaxed_match):
        result["verification_status"] = "verified"
        if strict_doc_match:
            notes.append("Certificate verified by QR and content match")
        else:
            notes.append("Certificate verified by reachable certificate page and relaxed metadata match")
    else:
        result["verification_status"] = "unverified"
        if name_required and not name_ok:
            notes.append("Student name does not strongly match certificate text")
        if not name_required:
            notes.append("Profile student name missing; strict name check skipped")
        if not title_ok:
            notes.append("Course title does not strongly match certificate text")
        if not authority_ok:
            notes.append("Certifying authority does not strongly match certificate text")
        if result["qr_url_accessible"] and not qr_page_valid:
            notes.append("QR URL reachable but certificate-page signals are weak")

    result["verification_notes"] = " | ".join(notes)[:2000]
    return result


def apply_course_certificate_verification(course, save=True):
    data = verify_course_certificate(course)
    for key, value in data.items():
        setattr(course, key, value)

    if save:
        course.save(
            update_fields=[
                "verification_status",
                "verification_notes",
                "verification_checked_at",
                "qr_detected",
                "qr_payload",
                "qr_url_checked",
                "qr_url_accessible",
            ]
        )
    return data
