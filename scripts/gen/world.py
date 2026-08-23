"""
The fictional world for the InsightHub tutorial.

EVERYTHING HERE IS INVENTED. Kestrel Bio, VELTRAXA (zoltarimab), the AURORA
trials, the competitor products and every clinical number below are fictional
and exist only so the tutorial has a self-consistent dataset. None of it is
medical information and none of it should ever be used for anything clinical.
"""

COMPANY = "Kestrel Bio"

PRODUCT = {
    "brand": "VELTRAXA",
    "inn": "zoltarimab",
    "class": "anti-TL1A monoclonal antibody",
    "indication": "moderate-to-severe ulcerative colitis (UC) in adults",
    "approval": "2025-09-12",
    "route": "IV induction (weeks 0, 4, 8) then subcutaneous 200 mg q4w maintenance",
}

# Fictional competitors.
COMPETITORS = {
    "RIMVEXA": {"inn": "dupilastat", "class": "oral selective JAK1 inhibitor"},
    "OBEXIVA": {"inn": "netrolimab", "class": "anti-integrin monoclonal antibody"},
    "ZOLVANTIS": {"inn": "briquimab", "class": "IL-23p19 inhibitor"},
}

TRIALS = {
    "AURORA-1": "Phase 3 induction study in moderate-to-severe UC (n=712)",
    "AURORA-2": "Phase 3 maintenance study, 52 weeks (n=498)",
    "AURORA-OLE": "Open-label extension, data through week 104",
    "HORIZON-CD": "Phase 2 in Crohn's disease, ongoing, topline expected 2027",
    "PEDIA-UC": "Planned pediatric study, 12-17 years, not yet enrolling",
    "REALIZE-UC": "Investigator-initiated real-world registry, 340 patients",
}

CONGRESSES = {
    "UEGW-2025": ("UEG Week 2025", "Barcelona", "2025-10-11"),
    "ECCO-2026": ("ECCO Congress 2026", "Vienna", "2026-02-18"),
    "DDW-2026": ("Digestive Disease Week 2026", "Chicago", "2026-05-16"),
}

# ---------------------------------------------------------------------------
# Insight taxonomy
# ---------------------------------------------------------------------------

CATEGORIES = {
    "EFFICACY_REAL_WORLD": "Observed effectiveness in routine practice, including onset, durability and loss of response.",
    "SAFETY_TOLERABILITY": "Tolerability, adverse events, monitoring burden, and safety perceptions.",
    "DOSING_ADMINISTRATION": "Dose, schedule, route, infusion logistics, device and self-administration.",
    "PATIENT_SELECTION_POSITIONING": "Which patients, at which line of therapy, and how the product is sequenced.",
    "COMPETITIVE_LANDSCAPE": "Comparisons, switching behaviour and perceptions of other agents.",
    "ACCESS_REIMBURSEMENT": "Formulary, prior authorisation, payer policy, cost and acquisition barriers.",
    "UNMET_NEED": "Clinical problems that remain unsolved for patients or clinicians.",
    "DATA_GAP_EVIDENCE_NEED": "Evidence the clinician says is missing and would change their behaviour.",
    "CLINICAL_TRIAL_EXPERIENCE": "Site-level experience with trials: enrolment, protocol burden, referrals.",
    "DIAGNOSTIC_MONITORING": "Biomarkers, endoscopic scoring, treat-to-target monitoring practice.",
    "GUIDELINES_PRACTICE_PATTERNS": "Guideline interpretation, institutional pathways, local protocols.",
    "PATIENT_EXPERIENCE_ADHERENCE": "Patient-reported burden, preference, adherence and support needs.",
}

NON_INSIGHT_LABELS = {
    "LOGISTICS": "Scheduling, travel, admin chatter with no medical content.",
    "SUMMARY_NO_INSIGHT": "A restatement of what the MSL presented, not what the HCP contributed.",
}

FLAGS = {
    "ADVERSE_EVENT": "Any mention of an adverse experience in a patient taking a Kestrel product.",
    "PRODUCT_COMPLAINT": "Any complaint about the physical product, device, packaging or quality.",
    "OFF_LABEL_REQUEST": "An unsolicited request for information outside the approved label.",
    "MEDICAL_INFORMATION_REQUEST": "A question requiring a formal Medical Information response.",
}

STRATEGIC_PRIORITIES = {
    "SP1": "Establish durability of response beyond one year",
    "SP2": "Support appropriate earlier-line positioning",
    "SP3": "Reduce access and prior-authorisation friction",
    "SP4": "Build the evidence base in difficult-to-treat populations",
    "SP5": "Improve the maintenance administration experience",
}

# ---------------------------------------------------------------------------
# Insight seeds
#
# Each seed is one underlying thing the field is hearing.  Multiple KOLs say it
# in different words, which is exactly what makes theme clustering non-trivial.
# `variants` are the surface forms that appear in call notes.
# ---------------------------------------------------------------------------

SEEDS = [
    # ---- Efficacy / durability -------------------------------------------
    dict(
        id="S01",
        category="EFFICACY_REAL_WORLD",
        canonical="Clinicians see a slower onset of symptomatic response with VELTRAXA than the trial data led them to expect, typically 6-8 weeks rather than 4.",
        priority="SP1",
        sentiment="negative",
        variants=[
            "He said his first four patients took closer to 8 weeks before they saw meaningful symptom improvement, which surprised him given how the AURORA-1 curves look.",
            "Feels the onset is slower than advertised - his impression is 6 to 8 weeks in practice vs the week 4 numbers he remembers from the label.",
            "Main comment was about speed of response. Said patients and referring docs get anxious around week 5 when nothing has changed yet.",
            "Noted a lag between starting induction and any real clinical change; said he now counsels patients to expect two months, not one.",
            "Raised that the trial response curves set an expectation of fast improvement that his own patients have not matched.",
        ],
    ),
    dict(
        id="S02",
        category="EFFICACY_REAL_WORLD",
        canonical="Durability beyond 12 months is the dominant question; clinicians want week-104 maintenance data before they commit patients long term.",
        priority="SP1",
        sentiment="neutral",
        variants=[
            "Wanted to know what happens after year one. Said the 52 week data is fine but every biologic looks good at 52 weeks.",
            "Asked repeatedly about two year durability. His view is that the decision point for UC biologics is month 18, not month 12.",
            "Says he cannot position it as a long term agent until he sees OLE data past 100 weeks.",
            "Durability came up again - he wants week 104 numbers, ideally with endoscopic outcomes not just clinical remission.",
            "Flagged that the maintenance dataset ends exactly where his clinical question begins.",
        ],
    ),
    dict(
        id="S03",
        category="EFFICACY_REAL_WORLD",
        canonical="Response in patients who previously failed two or more advanced therapies is perceived as markedly lower than in bio-naive patients.",
        priority="SP4",
        sentiment="negative",
        variants=[
            "In his hands the multiply-refractory patients are not responding. Bio-naive patients do well, third line and beyond much less so.",
            "Made the point that his practice is almost all bio-experienced and the AURORA population was not.",
            "Said the drug works beautifully in patients who have failed nothing and much less well in the ones he actually needs help with.",
            "Observed a clear split: naive patients respond, patients post two anti-TNFs and a JAK largely do not.",
        ],
    ),
    dict(
        id="S04",
        category="EFFICACY_REAL_WORLD",
        canonical="Several clinicians report secondary loss of response around months 9-12 and are asking whether dose escalation recovers it.",
        priority="SP1",
        sentiment="negative",
        variants=[
            "Two patients lost response at about month 10. Asked what the options are - escalate, shorten interval, or switch.",
            "Brought up secondary LOR. Said it feels like the same pattern he sees with anti-TNFs at the one year mark.",
            "Wanted to know if anyone has tried q2w dosing after loss of response and whether it recaptures anything.",
        ],
    ),
    # ---- Safety -----------------------------------------------------------
    dict(
        id="S05",
        category="SAFETY_TOLERABILITY",
        canonical="Injection site reactions with the maintenance syringe are more frequent and more bothersome than clinicians expected, driving some patients to consider stopping.",
        priority="SP5",
        sentiment="negative",
        flags=["ADVERSE_EVENT"],
        variants=[
            "Reported that three of his patients have had significant injection site reactions - redness and burning lasting several days. One is talking about stopping.",
            "ISRs came up unprompted. He said the label rate does not match what he is seeing and it is affecting adherence.",
            "One of his patients described the injection as stinging badly for a couple of minutes; she has developed a firm red area at the site each time.",
            "Says the injection site reactions are the single biggest tolerability complaint he hears at follow-up visits.",
        ],
    ),
    dict(
        id="S06",
        category="SAFETY_TOLERABILITY",
        canonical="Clinicians are uncertain how to counsel patients on infection risk relative to JAK inhibitors and want a clearer comparative safety story.",
        priority="SP2",
        sentiment="neutral",
        variants=[
            "Asked how the infection signal compares with RIMVEXA. Said his patients read about JAK warnings and assume all advanced therapies carry them.",
            "Wanted a plain answer on serious infection rates versus the oral agents. Felt the label alone does not let him have that conversation.",
            "Raised comparative safety - specifically herpes zoster - and whether prophylaxis or vaccination timing differs.",
        ],
    ),
    dict(
        id="S06b",
        category="SAFETY_TOLERABILITY",
        canonical="A cluster of clinicians report transient transaminase elevations during induction that resolve without intervention but trigger unnecessary work-up.",
        priority="SP4",
        sentiment="negative",
        flags=["ADVERSE_EVENT"],
        variants=[
            "Saw ALT rise to about 2x upper limit in two induction patients. Both normalised by week 12 without stopping, but he ordered a full hepatology work-up on the first one.",
            "Mentioned mild LFT bumps during induction. Not clinically significant in his view but it generates phone calls and repeat labs.",
            "Asked whether transient transaminitis in the first eight weeks is expected and whether he should be monitoring more or less often.",
        ],
    ),
    # ---- Dosing / administration ------------------------------------------
    dict(
        id="S07",
        category="DOSING_ADMINISTRATION",
        canonical="The IV induction phase is an operational bottleneck; infusion chair capacity is delaying initiation by several weeks at many centres.",
        priority="SP5",
        sentiment="negative",
        variants=[
            "Infusion capacity is his rate limiter. Says he can get approval in ten days and then wait a month for a chair.",
            "Complained that the IV induction means competing with oncology for infusion slots. That alone pushes him toward an oral first.",
            "Their unit runs at capacity; adding a three-infusion induction for each new UC start is not sustainable.",
            "Said if there were a fully subcutaneous induction he would use the drug in twice as many patients.",
        ],
    ),
    dict(
        id="S08",
        category="DOSING_ADMINISTRATION",
        canonical="Clinicians want guidance on restarting after an interrupted maintenance schedule (missed doses, surgery, pregnancy planning).",
        priority="SP5",
        sentiment="neutral",
        flags=["MEDICAL_INFORMATION_REQUEST"],
        variants=[
            "Asked what to do when a patient misses two maintenance doses - restart induction or resume q4w? Said the label is silent.",
            "Wanted written guidance on holding doses around elective colectomy and when to restart post-op.",
            "Requested information on management around pregnancy planning; he has two patients of childbearing age asking.",
        ],
    ),
    # ---- Positioning ------------------------------------------------------
    dict(
        id="S09",
        category="PATIENT_SELECTION_POSITIONING",
        canonical="Most clinicians currently place VELTRAXA in third line or later, largely by habit and formulary, not by clinical reasoning.",
        priority="SP2",
        sentiment="negative",
        variants=[
            "He uses it third line. When pushed on why, he said mostly because that is where the payer puts it, not because of the data.",
            "Positioning is post anti-TNF and post JAK in his practice. Admitted this is inertia as much as evidence.",
            "Said the drug sits behind two other agents in their pathway and nobody has revisited that pathway since it was written.",
            "In their algorithm it is a late option. He was open to moving it earlier if there were head to head data.",
        ],
    ),
    dict(
        id="S10",
        category="PATIENT_SELECTION_POSITIONING",
        canonical="Clinicians see a specific niche in patients with prominent extraintestinal manifestations and want data in that subgroup.",
        priority="SP4",
        sentiment="positive",
        variants=[
            "Thinks the mechanism should help the joint symptoms too. Asked if there is any EIM subgroup analysis.",
            "His two best responders both had significant arthralgia that also improved. Wants to know if that is real or coincidence.",
            "Suggested EIM patients as the natural population and was frustrated there is no published subgroup.",
        ],
    ),
    # ---- Competitive ------------------------------------------------------
    dict(
        id="S11",
        category="COMPETITIVE_LANDSCAPE",
        canonical="RIMVEXA's oral route and rapid onset are the main reasons clinicians choose it over VELTRAXA in newly diagnosed patients.",
        priority="SP2",
        sentiment="negative",
        variants=[
            "Says patients want a pill. RIMVEXA wins that conversation before efficacy is even discussed.",
            "For a newly diagnosed 28 year old he reaches for the oral agent because it works fast and needs no infusion visit.",
            "Convenience is beating mechanism in his clinic. The oral option is simply easier for everyone.",
            "Acknowledged the JAK safety concerns but said speed of response and route still win for most of his new starts.",
        ],
    ),
    dict(
        id="S12",
        category="COMPETITIVE_LANDSCAPE",
        canonical="Clinicians perceive the anti-TL1A class as promising but undifferentiated from IL-23 agents without head-to-head evidence.",
        priority="SP2",
        sentiment="neutral",
        variants=[
            "Asked directly how it differs from ZOLVANTIS in practice. Said without a head to head he treats them as interchangeable.",
            "Considers TL1A and IL-23 the same tier. Mechanism story is interesting but not decision-changing for him.",
            "Wants a comparative trial. Said network meta-analyses do not move him.",
        ],
    ),
    # ---- Access -----------------------------------------------------------
    dict(
        id="S13",
        category="ACCESS_REIMBURSEMENT",
        canonical="Prior authorisation typically requires documented failure of two advanced therapies, which locks the product into late lines.",
        priority="SP3",
        sentiment="negative",
        variants=[
            "PA requires two prior advanced therapy failures at both his major payers. That is why it is third line.",
            "His nurse spends about 90 minutes per new start on the authorisation paperwork. Two denials so far this quarter.",
            "Said the step edit is the whole story on positioning. Change the step edit and his prescribing changes.",
            "Payer policy at the regional plan mandates prior anti-TNF and prior JAK failure before approval.",
        ],
    ),
    dict(
        id="S14",
        category="ACCESS_REIMBURSEMENT",
        canonical="Buy-and-bill economics for the IV induction are unattractive to community practices, pushing patients to hospital outpatient settings.",
        priority="SP3",
        sentiment="negative",
        variants=[
            "The community group next door will not stock it - the acquisition cost versus reimbursement does not work for them.",
            "Said his private practice colleagues send patients to the hospital for induction because the buy and bill margin is negative.",
            "Raised the site of care issue. Community practices are opting out entirely.",
        ],
    ),
    # ---- Unmet need -------------------------------------------------------
    dict(
        id="S15",
        category="UNMET_NEED",
        canonical="Acute severe UC and the steroid-refractory inpatient remain the biggest unmet need; nobody has data there.",
        priority="SP4",
        sentiment="neutral",
        variants=[
            "His real problem is the hospitalised steroid refractory patient. Nothing in the class has data there.",
            "Said the unmet need is ASUC, not the outpatient with moderate disease.",
            "Wants to know if anyone is even thinking about an inpatient rescue study.",
        ],
    ),
    dict(
        id="S16",
        category="UNMET_NEED",
        canonical="Patients with prior colectomy or pouchitis are excluded from every trial and clinicians have no evidence to guide them.",
        priority="SP4",
        sentiment="neutral",
        variants=[
            "Asked about pouchitis. Said he has a dozen patients with chronic pouchitis and zero evidence for any of them.",
            "Pouch patients are invisible in all the programmes. He treats them off label with whatever he has.",
            "Raised post-colectomy patients as a completely unserved group.",
        ],
    ),
    # ---- Data gaps --------------------------------------------------------
    dict(
        id="S17",
        category="DATA_GAP_EVIDENCE_NEED",
        canonical="Clinicians want histologic remission endpoints, not just clinical and endoscopic, and increasingly regard histology as the real target.",
        priority="SP1",
        sentiment="neutral",
        variants=[
            "Asked whether AURORA-2 captured histologic remission. Said that is the endpoint his academic colleagues now argue for.",
            "Histology is where the field is going. He wants to see Geboes or Nancy index data.",
            "Said endoscopic improvement is table stakes now and histologic remission is the differentiator.",
        ],
    ),
    dict(
        id="S18",
        category="DATA_GAP_EVIDENCE_NEED",
        canonical="There is no guidance on therapeutic drug monitoring or target trough concentrations for zoltarimab.",
        priority="SP1",
        sentiment="neutral",
        flags=["MEDICAL_INFORMATION_REQUEST"],
        variants=[
            "Asked if there is a target trough. He does TDM routinely for anti-TNFs and wants to do the same here.",
            "Wanted to know whether an assay exists and whether levels correlate with response.",
            "Said without TDM he cannot tell mechanical failure from immunogenicity when someone loses response.",
        ],
    ),
    dict(
        id="S19",
        category="DATA_GAP_EVIDENCE_NEED",
        canonical="Immunogenicity and anti-drug antibody rates, and whether concomitant immunomodulators are needed, are unresolved questions.",
        priority="SP1",
        sentiment="neutral",
        variants=[
            "Asked about ADA rates and whether he should be co-prescribing an immunomodulator as he would with infliximab.",
            "Immunogenicity question again - is combination therapy needed or is monotherapy sufficient?",
            "Wants the ADA data broken out by whether patients were on a thiopurine.",
        ],
    ),
    # ---- Trial experience -------------------------------------------------
    dict(
        id="S20",
        category="CLINICAL_TRIAL_EXPERIENCE",
        canonical="The HORIZON-CD protocol's endoscopy schedule is a major barrier to enrolment at community and mid-sized sites.",
        priority="SP4",
        sentiment="negative",
        variants=[
            "Said the HORIZON-CD scope schedule is the reason he has enrolled one patient. Four scopes in a year is a hard sell.",
            "Enrolment is stalled because of the endoscopy burden. His scheduling team cannot absorb it.",
            "Protocol burden came up - specifically the number of colonoscopies and the central reading turnaround.",
        ],
    ),
    dict(
        id="S21",
        category="CLINICAL_TRIAL_EXPERIENCE",
        canonical="Sites want a clearer referral pathway; community gastroenterologists do not know which trials are open.",
        priority="SP4",
        sentiment="neutral",
        variants=[
            "Asked for a simple one page list of open studies he can hand to referring physicians.",
            "Said his referral network has no idea what is enrolling. Referrals dried up after the last study closed.",
        ],
    ),
    # ---- Diagnostics ------------------------------------------------------
    dict(
        id="S22",
        category="DIAGNOSTIC_MONITORING",
        canonical="Faecal calprotectin is being used as the primary treat-to-target monitor, replacing routine endoscopy in practice.",
        priority="SP1",
        sentiment="neutral",
        variants=[
            "He monitors with calprotectin every 12 weeks and scopes only if it rises. Endoscopy is a last resort now.",
            "Said calprotectin is his de facto endpoint and asked whether it tracks with response in the AURORA data.",
            "Their pathway is calpro-driven. Wanted the correlation between calprotectin and endoscopic outcome in the trials.",
        ],
    ),
    dict(
        id="S23",
        category="DIAGNOSTIC_MONITORING",
        canonical="Clinicians would use a predictive biomarker to select patients for anti-TL1A therapy if one existed.",
        priority="SP4",
        sentiment="positive",
        variants=[
            "Asked whether TL1A expression predicts response and whether there is a companion assay in development.",
            "Said a biomarker would change everything - he would move it first line for a marker-positive patient tomorrow.",
            "Very interested in the predictive biomarker work presented at ECCO. Wants to know if it is being taken forward.",
        ],
    ),
    # ---- Guidelines -------------------------------------------------------
    dict(
        id="S24",
        category="GUIDELINES_PRACTICE_PATTERNS",
        canonical="Institutional pathways are updated only annually, so newly approved agents wait up to a year before they can be used routinely.",
        priority="SP2",
        sentiment="negative",
        variants=[
            "Their P&T committee reviews the IBD pathway once a year in November. Until then it is exception requests only.",
            "Said the pathway is the gatekeeper, not the individual physician. He cannot deviate without a form.",
            "Institutional protocol has not been revised since before approval so it is not in there at all.",
        ],
    ),
    dict(
        id="S25",
        category="GUIDELINES_PRACTICE_PATTERNS",
        canonical="Clinicians expect the next society guideline update to be the trigger for repositioning advanced therapies and are waiting for it.",
        priority="SP2",
        sentiment="neutral",
        variants=[
            "Said he is waiting for the guideline refresh before changing sequencing. Expects it after DDW.",
            "Guidelines drive his group. Nothing moves until the society statement moves.",
        ],
    ),
    # ---- Patient experience -----------------------------------------------
    dict(
        id="S26",
        category="PATIENT_EXPERIENCE_ADHERENCE",
        canonical="The autoinjector is difficult for patients with reduced hand strength, and there is demand for a different device.",
        priority="SP5",
        sentiment="negative",
        flags=["PRODUCT_COMPLAINT"],
        variants=[
            "Two elderly patients cannot depress the autoinjector plunger. One gave up and the daughter now does it.",
            "Device feedback - his patients with arthritis struggle with the activation force. He asked if a different presentation is planned.",
            "Said the pen is stiff. A patient reported the cap was extremely hard to remove and she cracked it trying.",
        ],
    ),
    dict(
        id="S27",
        category="PATIENT_EXPERIENCE_ADHERENCE",
        canonical="Patients underestimate the importance of maintenance dosing once they feel well, and clinicians want better adherence support materials.",
        priority="SP5",
        sentiment="neutral",
        variants=[
            "Adherence drops off once patients feel better. He wants something patient-facing that explains why maintenance matters.",
            "Said his no-show rate for maintenance is climbing among patients in remission.",
            "Asked whether there is a patient support programme with reminders. Did not know one existed.",
        ],
    ),
]

# A handful of decoy / noise topics that look insight-shaped but are not.
NOISE_SENTENCES = [
    "Coffee was terrible, as usual.",
    "Rescheduled from last Tuesday due to his clinic overrunning.",
    "He was 20 minutes late; we had about 25 minutes in total.",
    "Confirmed his assistant is Marta, best route in for future scheduling.",
    "Parking at the medical centre is a nightmare, allow extra time.",
    "He is travelling to the congress and offered to meet there.",
    "Reminded him about the advisory board invitation, he will check dates.",
    "We reviewed the AURORA-1 primary endpoint slides.",
    "Walked through the mechanism of action deck, no questions.",
    "Shared the published induction manuscript reprint.",
    "Discussed the standard response document on infusion reactions.",
    "Follow up: send him the reprint and the trial site list.",
    "Next steps: schedule a follow up in Q3.",
    "He asked to be removed from the newsletter distribution.",
]

MSLS = [
    {"id": "MSL-01", "name": "R. Okafor", "region": "US-East", "style": "bullets"},
    {"id": "MSL-02", "name": "S. Lindqvist", "region": "EMEA", "style": "narrative"},
    {"id": "MSL-03", "name": "D. Cheng", "region": "US-West", "style": "telegraphic"},
    {"id": "MSL-04", "name": "A. Ferreira", "region": "EMEA", "style": "template"},
    {"id": "MSL-05", "name": "M. Haddad", "region": "US-Central", "style": "narrative"},
    {"id": "MSL-06", "name": "J. Whitcombe", "region": "US-East", "style": "bullets"},
    {"id": "MSL-07", "name": "P. Raman", "region": "APAC", "style": "template"},
    {"id": "MSL-08", "name": "L. Novak", "region": "EMEA", "style": "telegraphic"},
]

INTERACTION_TYPES = [
    "1:1 meeting",
    "Virtual call",
    "Congress interaction",
    "Advisory board follow-up",
    "Investigator meeting",
    "Unsolicited inbound",
]

INSTITUTIONS = [
    ("Northgate University Hospital", "US-East"),
    ("Brightwater Medical Center", "US-East"),
    ("Cedar Ridge Health System", "US-Central"),
    ("Lakeshore Gastroenterology Associates", "US-Central"),
    ("Pacific Crest Medical Center", "US-West"),
    ("Sunridge Digestive Institute", "US-West"),
    ("St. Aldric's Hospital", "EMEA"),
    ("Universitätsklinikum Rheinfeld", "EMEA"),
    ("Hôpital Saint-Brieuc-sur-Loire", "EMEA"),
    ("Karolinska-Vasa IBD Unit", "EMEA"),
    ("Royal Thornbury Infirmary", "EMEA"),
    ("Meridian General Hospital", "APAC"),
    ("Harbourview Institute of Digestive Health", "APAC"),
    ("Ashgrove Community GI", "US-East"),
    ("Fairmount Colorectal Group", "US-West"),
]

SPECIALTIES = [
    "Gastroenterology - IBD",
    "Gastroenterology - General",
    "Colorectal Surgery",
    "Pediatric Gastroenterology",
    "IBD Advanced Practice Nurse",
    "Clinical Pharmacology",
]

SURNAMES = [
    "Achterberg", "Bello", "Castellanos", "Duvall", "Eriksen", "Farrow", "Grigoryan",
    "Halvorsen", "Iyengar", "Jelinek", "Kowalczyk", "Larue", "Maddox", "Nkemdirim",
    "Ostrowski", "Pemberton", "Quintero", "Rasmussen", "Saito", "Thibault", "Ulrich",
    "Vandermeer", "Wexler", "Xu", "Yilmaz", "Zambrano", "Aldridge", "Baptiste",
    "Corrigan", "Dziedzic", "Espinoza", "Fitzharris", "Gallardo", "Hollingsworth",
    "Imhoff", "Janowski", "Kirkbride", "Lindqvist", "Moreau", "Nystrom",
]

FIRST_INITIALS = list("ABCDEFGHIJKLMNOPRSTVW")
