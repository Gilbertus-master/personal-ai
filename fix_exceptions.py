#!/usr/bin/env python3
"""Fix bare except statements in app/api/main.py"""

with open('app/api/main.py', 'r') as f:
    content = f.read()

# Fix 1: cost_fetch_failed (lines ~702-703)
old1 = """    except Exception:
        pass
    return {}


def _apply_channel_defaults"""

new1 = """    except Exception as exc:
        import structlog
        structlog.get_logger(__name__).warning(
            "cost_fetch_failed",
            module=module,
            error=str(exc),
        )
    return {}


def _apply_channel_defaults"""

content = content.replace(old1, new1)

# Fix 2: answer_cache_write_failed (in _save_answer_cache)
old2 = """            conn.commit()
    except Exception:
        pass




@app.post("/ask"""

new2 = """            conn.commit()
    except Exception as exc:
        import structlog
        structlog.get_logger(__name__).warning(
            "answer_cache_write_failed",
            cache_key=cache_key,
            error=str(exc),
        )




@app.post("/ask"""

content = content.replace(old2, new2)

# Fix 3: evaluation_persistence_failed (nested exception)
old3 = """                except Exception:
                    pass  # feedback persistence is non-critical
            timer.end("evaluate")"""

new3 = """                except Exception as exc:
                    import structlog
                    structlog.get_logger(__name__).debug(
                        "evaluation_persistence_failed",
                        error=str(exc),
                    )
            timer.end("evaluate")"""

content = content.replace(old3, new3)

# Fix 4: evaluator_failed (outer exception) - already done
# Just ensure it's there if not

if "evaluator_failed" not in content:
    old4 = """            timer.end("evaluate")
        except Exception:
            pass  # evaluator jest opcjonalny — nie blokuj głównego flow"""
    new4 = """            timer.end("evaluate")
        except Exception as exc:
            import structlog
            structlog.get_logger(__name__).debug(
                "evaluator_failed",
                error=str(exc),
            )"""
    content = content.replace(old4, new4)

with open('app/api/main.py', 'w') as f:
    f.write(content)

print("Done fixing exceptions")
