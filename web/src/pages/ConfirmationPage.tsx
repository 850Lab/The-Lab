import { LayoutGroup, motion } from "framer-motion";
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ContinueCTA } from "@/components/ContinueCTA";
import {
  DisputeGroupCard,
  type DisputeGroupItem,
} from "@/components/DisputeGroupCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { setWorkflowStep } from "@/lib/workflow";

type GroupModel = {
  id: string;
  title: string;
  items: (DisputeGroupItem & { order: number })[];
};

function buildInitialGroups(): GroupModel[] {
  let order = 0;
  const next = () => order++;

  return [
    {
      id: "collections",
      title: "Collections",
      items: [
        {
          id: "col-1",
          company: "ABC Recovery",
          issueLabel: "We’ll challenge this account",
          order: next(),
        },
        {
          id: "col-2",
          company: "Metro Medical Billing",
          issueLabel: "We’ll challenge this account",
          order: next(),
        },
        {
          id: "col-3",
          company: "Summit Collections",
          issueLabel: "We’ll challenge this account",
          order: next(),
        },
      ],
    },
    {
      id: "chargeoffs",
      title: "Charge-offs",
      items: [
        {
          id: "co-1",
          company: "Harbor Retail Card",
          issueLabel: "We’ll challenge this balance",
          order: next(),
        },
        {
          id: "co-2",
          company: "Northwind Auto Finance",
          issueLabel: "We’ll challenge this balance",
          order: next(),
        },
      ],
    },
    {
      id: "lates",
      title: "Late payments",
      items: [
        {
          id: "lp-1",
          company: "First Community Bank",
          issueLabel: "We’ll challenge this late mark",
          order: next(),
        },
        {
          id: "lp-2",
          company: "Brightway Credit Card",
          issueLabel: "We’ll challenge this late mark",
          order: next(),
        },
        {
          id: "lp-3",
          company: "Union Auto Loan",
          issueLabel: "We’ll challenge this late mark",
          order: next(),
        },
        {
          id: "lp-4",
          company: "ShopMart Store Card",
          issueLabel: "We’ll challenge this late mark",
          order: next(),
        },
      ],
    },
  ];
}

type RemovedSnapshot = {
  groupId: string;
  item: DisputeGroupItem & { order: number };
};

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.06 },
  },
};

const headerVariants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

const groupListVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.14, delayChildren: 0.04 },
  },
};

const groupCardVariants = {
  hidden: { opacity: 0, y: 22 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.48, ease: [0.22, 1, 0.36, 1] },
  },
};

export function ConfirmationPage() {
  const navigate = useNavigate();
  const [groups, setGroups] = useState<GroupModel[]>(() => buildInitialGroups());
  const [lastRemoved, setLastRemoved] = useState<RemovedSnapshot | null>(null);

  const removeItem = useCallback((groupId: string, itemId: string) => {
    setGroups((prev) => {
      const g = prev.find((x) => x.id === groupId);
      const item = g?.items.find((i) => i.id === itemId);
      if (item) {
        setLastRemoved({ groupId, item: { ...item } });
      }
      return prev.map((gr) =>
        gr.id === groupId ? { ...gr, items: gr.items.filter((i) => i.id !== itemId) } : gr
      );
    });
  }, []);

  const undoRemove = useCallback(() => {
    if (!lastRemoved) return;
    const { groupId, item } = lastRemoved;
    setGroups((prev) =>
      prev.map((gr) =>
        gr.id === groupId ? { ...gr, items: [...gr.items, item].sort((a, b) => a.order - b.order) } : gr
      )
    );
    setLastRemoved(null);
  }, [lastRemoved]);

  const handleContinue = () => {
    setWorkflowStep("strategy");
    navigate("/strategy", { replace: true });
  };

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[30%] z-0 h-[min(55vw,380px)] w-[min(55vw,380px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.05] blur-[100px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-xl px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        <LayoutGroup>
          <motion.div variants={pageVariants} initial="hidden" animate="show">
            <motion.p
              variants={headerVariants}
              className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
            >
              Review
            </motion.p>

            <motion.h1
              variants={headerVariants}
              className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-3xl"
            >
              We’ve prepared this for you
            </motion.h1>

            <motion.p
              variants={headerVariants}
              className="mx-auto mt-3 max-w-md text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
            >
              These are the items we’ll challenge to improve your credit
            </motion.p>

            <motion.p
              variants={headerVariants}
              className="mx-auto mt-4 max-w-sm text-center text-xs leading-relaxed text-lab-subtle sm:text-sm"
            >
              Most people continue with these as-is
            </motion.p>

            <motion.div
              variants={groupListVariants}
              className="mt-10 space-y-8 sm:mt-12 sm:space-y-10"
            >
              {groups.map((g) => (
                <DisputeGroupCard
                  key={g.id}
                  title={g.title}
                  items={g.items}
                  onRemoveItem={(itemId) => removeItem(g.id, itemId)}
                  groupVariants={groupCardVariants}
                />
              ))}
            </motion.div>

            {lastRemoved ? (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 flex justify-center"
              >
                <button
                  type="button"
                  onClick={undoRemove}
                  className="text-sm font-medium text-lab-accent/90 transition-colors hover:text-lab-accent"
                >
                  Undo
                </button>
              </motion.div>
            ) : null}

            <motion.div variants={headerVariants} className="mt-12 sm:mt-14">
              <ContinueCTA onClick={handleContinue} />
            </motion.div>
          </motion.div>
        </LayoutGroup>
      </main>
    </div>
  );
}
