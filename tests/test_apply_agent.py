import apply_agent


def test_is_clean_ats_by_ats_field():
    assert apply_agent.is_clean_ats({"ats": "greenhouse"})
    assert apply_agent.is_clean_ats({"ats": "Lever"})
    assert apply_agent.is_clean_ats({"ats": "ashby"})
    assert not apply_agent.is_clean_ats({"ats": "workday"})
    assert not apply_agent.is_clean_ats({"ats": "phenom"})


def test_is_clean_ats_by_apply_url_domain():
    assert apply_agent.is_clean_ats({"ats": "", "apply_url": "https://jobs.ashbyhq.com/gamma/x"})
    assert apply_agent.is_clean_ats({"ats": "", "apply_url": "https://boards.greenhouse.io/acme/jobs/1"})
    assert not apply_agent.is_clean_ats({"ats": "", "apply_url": "https://acme.wd1.myworkdayjobs.com/x"})


def test_is_clean_ats_reads_nested_job():
    assert apply_agent.is_clean_ats({"jobs": {"ats": "lever"}})
    assert not apply_agent.is_clean_ats({"jobs": {"ats": "smartrecruiters"}})
