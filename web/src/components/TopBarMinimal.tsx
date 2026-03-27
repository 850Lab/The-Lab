import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { useAuth } from "@/providers/AuthContext";

export function TopBarMinimal() {
  const { token, user, signOut } = useAuth();

  return (
    <motion.header
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="fixed left-0 right-0 top-0 z-40 border-b border-white/[0.06] bg-lab-surface/75 backdrop-blur-md"
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
        <span className="text-[15px] font-semibold tracking-tight text-lab-text">
          850 Lab
        </span>
        <div className="flex min-w-0 items-center gap-3 text-sm">
          {token ? (
            <>
              <span
                className="hidden max-w-[160px] truncate text-lab-muted sm:inline"
                title={user?.email}
              >
                {user?.email}
              </span>
              <button
                type="button"
                onClick={() => void signOut()}
                className="shrink-0 font-medium text-lab-accent hover:text-sky-300"
              >
                Sign out
              </button>
            </>
          ) : (
            <Link
              to="/login"
              className="font-medium text-lab-accent hover:text-sky-300"
            >
              Sign in
            </Link>
          )}
        </div>
      </div>
    </motion.header>
  );
}
