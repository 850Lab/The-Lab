/**
 * GTM preview registry — status, routes, and declared integrations.
 * Edit here as pages ship; remove `/launch-preview` when obsolete.
 */

export type GtmPageStatus = "done" | "processing" | "planned";

export type GtmVerification =
  | {
      mode: "declared";
      location: string;
      note?: string;
    }
  | {
      mode: "api_get";
      path: string;
      okIf: "2xx" | "401" | "2xx_or_401" | "any_http";
      bearer?: "optional" | "required";
    };

export type GtmConnection = {
  id: string;
  name: string;
  description: string;
  verification: GtmVerification;
};

export type GtmPreviewPage = {
  slug: string;
  label: string;
  description: string;
  status: GtmPageStatus;
  path?: string;
  audience?: string;
  previewNotes?: string;
  /** processing: work in flight */
  activeWork?: { summary: string; paths: string[] };
  plannedTarget?: string;
  connections: GtmConnection[];
};

export function pathToSlug(routePath: string): string {
  if (routePath === "/") return "home";
  return routePath.replace(/^\//, "").replace(/\//g, "-");
}

const API_DIST_OK: GtmConnection = {
  id: "api-customer-web-status",
  name: "API + customer web bundle",
  description: "FastAPI serves SPA and reports dist health",
  verification: {
    mode: "api_get",
    path: "/api/system/customer-web-status",
    okIf: "2xx",
  },
};

function c(id: string, name: string, description: string, v: GtmVerification): GtmConnection {
  return { id, name, description, verification: v };
}

function shell(file: string, note?: string): GtmConnection {
  return c(
    `declared-${file.replace(/[^a-z0-9]+/gi, "-")}`,
    "Frontend module",
    note ?? "Part of this page’s render tree",
    { mode: "declared", location: file },
  );
}

function spaDeclared(path: string): GtmConnection {
  return c(`spa-${pathToSlug(path)}`, "React route", `Router path ${path}`, {
    mode: "declared",
    location: `web/src/App.tsx`,
    note: `Route → ${path}`,
  });
}

function customerShell(): GtmConnection[] {
  return [
    shell("web/src/components/CustomerWorkflowShell.tsx", "Auth + workflow guards"),
    shell("web/src/providers/CustomerWorkflowContext.tsx", "Workflow session + canonical path"),
    shell("web/src/providers/AuthContext.tsx", "Session token + /api/auth/me"),
  ];
}

function orgProgramShell(): GtmConnection[] {
  return [
    shell("web/src/components/ProgramShell.tsx", "Program nav + layout"),
    shell("web/src/providers/AuthContext.tsx", "Bearer for /api/me/*"),
  ];
}

function meOrgProgramConn(): GtmConnection {
  return c("api-me-org-program", "GET /api/me/org-program", "Org membership + enrollment context", {
    mode: "api_get",
    path: "/api/me/org-program",
    okIf: "2xx_or_401",
    bearer: "optional",
  });
}

function meProgressConn(): GtmConnection {
  return c("api-me-progress", "GET /api/me/progress", "Program milestones + instructor state", {
    mode: "api_get",
    path: "/api/me/progress",
    okIf: "2xx_or_401",
    bearer: "optional",
  });
}

function doneCustomer(
  path: string,
  label: string,
  description: string,
  extra: GtmConnection[] = [],
  notes?: string,
): GtmPreviewPage {
  return {
    slug: pathToSlug(path),
    path,
    label,
    description,
    status: "done",
    audience: "signed_in_consumer",
    previewNotes: notes,
    connections: [spaDeclared(path), ...customerShell(), API_DIST_OK, ...extra],
  };
}

function donePublic(path: string, label: string, description: string, extra: GtmConnection[] = []): GtmPreviewPage {
  return {
    slug: pathToSlug(path),
    path,
    label,
    description,
    status: "done",
    audience: "public",
    connections: [spaDeclared(path), shell("web/src/providers/AuthContext.tsx"), API_DIST_OK, ...extra],
  };
}

function doneOrgParticipant(path: string, label: string, description: string, extra: GtmConnection[] = []): GtmPreviewPage {
  return {
    slug: pathToSlug(path),
    path,
    label,
    description,
    status: "done",
    audience: "org_participant",
    connections: [
      spaDeclared(path),
      ...orgProgramShell(),
      meOrgProgramConn(),
      meProgressConn(),
      API_DIST_OK,
      ...extra,
    ],
  };
}

function doneOrgStaff(path: string, label: string, description: string, audience: string, extra: GtmConnection[] = []): GtmPreviewPage {
  return {
    slug: pathToSlug(path),
    path,
    label,
    description,
    status: "done",
    audience,
    connections: [
      spaDeclared(path),
      ...orgProgramShell(),
      meOrgProgramConn(),
      API_DIST_OK,
      c(
        "api-orgs",
        "Org APIs",
        "PATCH/GET /api/orgs/{id}* (instructor/admin)",
        {
          mode: "declared",
          location: "api/workflow_app.py",
          note: "Requires org role + session",
        },
      ),
      ...extra,
    ],
  };
}

const PAGES: GtmPreviewPage[] = [
  {
    slug: "home",
    path: "/",
    label: "Home gate",
    description: "Routes signed-in users into workflow or program context.",
    status: "done",
    audience: "signed_in_consumer",
    connections: [
      spaDeclared("/"),
      ...customerShell(),
      shell("web/src/pages/HomeGate.tsx"),
      API_DIST_OK,
      c("api-auth-me", "GET /api/auth/me", "Hydrates session on load", {
        mode: "api_get",
        path: "/api/auth/me",
        okIf: "2xx_or_401",
        bearer: "optional",
      }),
    ],
  },
  donePublic("/login", "Login", "Email/password → session token", [
    c("api-login", "POST /api/auth/login", "Declared (POST — not probed as GET)", {
      mode: "declared",
      location: "api/workflow_app.py → post_auth_login",
    }),
      c("api-me", "GET /api/auth/me", "Session check", {
        mode: "api_get",
        path: "/api/auth/me",
        okIf: "2xx_or_401",
        bearer: "optional",
      }),
  ]),
  donePublic("/signup", "Signup", "Account creation + verification email", [
    c("api-signup", "POST /api/auth/signup", "Declared", {
      mode: "declared",
      location: "api/workflow_app.py → post_auth_signup",
    }),
  ]),
  doneCustomer("/verify-email", "Verify email", "Verification code entry", [], "Needs unverified session."),
  {
    slug: pathToSlug("/demo"),
    path: "/demo",
    label: "Public demo",
    description: "Redirects to home #live-demo; same fixtures on landing.",
    status: "done",
    audience: "public",
    connections: [
      spaDeclared("/demo"),
      shell("web/src/pages/LandingFirstTime.tsx"),
      shell("web/src/components/PublicDemoInteractiveSection.tsx"),
      API_DIST_OK,
      c("api-demo-scenarios", "GET /api/public/demo/scenarios", "Fixture list", {
        mode: "api_get",
        path: "/api/public/demo/scenarios",
        okIf: "any_http",
      }),
    ],
  },
  doneCustomer("/get-report", "Report acquisition", "Start of report acquisition funnel"),
  doneCustomer("/get-report/idiq", "IDIQ bridge", "IDIQ-specific bridge"),
  doneCustomer("/upload", "Upload", "Consumer workflow — PDF upload", [
    c("wf", "workflow_sessions + steps", "Declared backend", {
      mode: "declared",
      location: "services/workflow/*, workflow_schema.py",
    }),
  ]),
  doneCustomer("/analyze", "Analyze", "Analysis / review claims step"),
  doneCustomer("/prepare", "Prepare", "Confirmation before strategy"),
  doneCustomer("/strategy", "Strategy", "Dispute strategy UX"),
  doneCustomer("/payment", "Payment", "Checkout / credits", [
    c("pay", "Payment APIs", "Declared", {
      mode: "declared",
      location: "services/workflow_payment_service.py, api/workflow_app.py",
    }),
  ]),
  doneCustomer("/letters", "Letters ready", "Generated letters"),
  doneCustomer("/proof", "Proof", "Proof / signature step"),
  doneCustomer("/send", "Send", "Mailing / Lob context"),
  doneCustomer("/tracking", "Tracking", "Outbound tracking"),
  doneCustomer("/responses", "Responses", "Response intake"),
  doneCustomer("/escalation", "Escalation", "Escalation overview"),
  doneCustomer("/escalation-action", "Escalation action", "Escalation action step"),
  doneOrgParticipant("/program", "Program home", "Path map + progress + access state"),
  doneOrgParticipant("/program/upload", "Program upload", "Org-scoped report upload", [
    c("me-report", "POST /api/me/report", "Declared multipart", {
      mode: "declared",
      location: "api/workflow_app.py → post_me_report",
    }),
  ]),
  doneOrgParticipant("/program/findings", "Program findings", "Findings for org report", [
    c("me-findings", "GET /api/me/report/findings", "Probable GET", {
      mode: "api_get",
      path: "/api/me/report/findings",
      okIf: "2xx_or_401",
      bearer: "optional",
    }),
  ]),
  doneOrgParticipant("/program/select", "Program disputes", "Dispute selections", [
    c("me-sel", "GET/POST /api/me/dispute-*", "Declared", {
      mode: "declared",
      location: "services/me_org_dispute_service.py",
    }),
  ]),
  doneOrgParticipant("/program/letters", "Program letters", "Letter generation in org context", [
    c("me-letters", "POST /api/me/generate-letters", "Declared", {
      mode: "declared",
      location: "api/workflow_app.py",
    }),
  ]),
  doneOrgParticipant("/program/progress", "Program status", "Milestones + instructor dual-state"),
  doneOrgStaff("/program/setup", "Org setup", "Onboarding profile PATCH", "org_instructor"),
  doneOrgStaff("/program/instructor", "Guide desk", "Cohort + workshops", "org_instructor", [
    c("parts", "GET /api/orgs/.../participants", "Declared", {
      mode: "declared",
      location: "services/org_program_visibility_service.py",
    }),
  ]),
  doneOrgStaff("/program/org-insights", "Program overview", "Buyer cohort dashboard", "org_admin"),
  {
    slug: pathToSlug("/mission-control"),
    path: "/mission-control",
    label: "Mission Control",
    description: "Operator workflows, leads, exceptions (not GTM customer).",
    status: "done",
    audience: "internal_mc",
    previewNotes: "Uses X-Workflow-Admin-Key header.",
    connections: [
      spaDeclared("/mission-control"),
      shell("web/src/pages/mission-control/*"),
      c("mc-api", "Internal admin routes", "Bearer admin key", {
        mode: "declared",
        location: "GET /internal/admin/*",
        note: "Not probed from browser without key",
      }),
      API_DIST_OK,
    ],
  },
  {
    slug: "processing-org-invites",
    label: "Org invites & self-serve signup",
    description: "Organizations invite users without platform-admin user IDs.",
    status: "processing",
    path: "/program/setup",
    activeWork: {
      summary: "APIs partially exist; UX for email invites not wired in SPA.",
      paths: [
        "api/workflow_app.py — org + enrollment routes",
        "services/org_service.py",
        "web/src/pages/program/ProgramOrgSetupPage.tsx",
      ],
    },
    connections: [
      c("stub", "Planned endpoints", "Invite tokens, accept flow", {
        mode: "declared",
        location: "(planned) services/* + new routes",
        note: "In progress",
      }),
      meOrgProgramConn(),
      API_DIST_OK,
    ],
  },
  {
    slug: "processing-session-roster-ui",
    label: "Session roster assignment UI",
    description: "Assign enrollments to workshop sessions inside the SPA.",
    status: "processing",
    path: "/program/instructor",
    activeWork: {
      summary: "Backend POST …/enrollments/{id}/session exists; roster UI pending.",
      paths: [
        "api/workflow_app.py — post_org_enrollment_session",
        "web/src/pages/program/OrgDeliveryDashboardPage.tsx",
      ],
    },
    connections: [
      c("api", "POST /api/orgs/{id}/enrollments/{eid}/session", "Declared", {
        mode: "declared",
        location: "api/workflow_app.py",
      }),
      API_DIST_OK,
    ],
  },
  {
    slug: "planned-gameplan-stage",
    label: "Gameplan program stage",
    description: "Visible step after letters (credit command plan parity).",
    status: "planned",
    plannedTarget: "Participant UX",
    connections: [
      c("future", "PROGRAM_STEPS extension", "Backend milestone list", {
        mode: "declared",
        location: "services/program_progress_service.py",
        note: "Not built",
      }),
    ],
  },
  {
    slug: "planned-live-presence",
    label: "Live workshop presence",
    description: "Synchronized room state (who is on which step, live).",
    status: "planned",
    plannedTarget: "Workshops",
    connections: [
      c("future", "WebSocket or polling", "Not present", {
        mode: "declared",
        location: "(planned)",
      }),
    ],
  },
  {
    slug: "planned-billing-seats",
    label: "Integrated billing & seats",
    description: "Real subscriptions vs payment_access flag.",
    status: "planned",
    plannedTarget: "Monetization",
    connections: [
      c("flag", "organizations.payment_access", "Current gate", {
        mode: "declared",
        location: "workflow_schema.py, org_service.py",
      }),
    ],
  },
];

export const GTM_PREVIEW_PAGES: GtmPreviewPage[] = PAGES;

export function getGtmPageBySlug(slug: string): GtmPreviewPage | undefined {
  return GTM_PREVIEW_PAGES.find((p) => p.slug === slug);
}

export function countByStatus(): Record<GtmPageStatus, number> {
  return GTM_PREVIEW_PAGES.reduce(
    (acc, p) => {
      acc[p.status] += 1;
      return acc;
    },
    { done: 0, processing: 0, planned: 0 } as Record<GtmPageStatus, number>,
  );
}

/** @deprecated use GTM_PREVIEW_PAGES filtered by status */
export const LAUNCH_PREVIEW_COMING_SOON = GTM_PREVIEW_PAGES.filter((p) => p.status === "planned").map(
  (p) => ({
    label: p.label,
    description: p.description,
    target: p.plannedTarget,
  }),
);
