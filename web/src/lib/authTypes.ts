export type AuthUser = {
  id: number;
  email: string;
  displayName: string | null;
  role: string;
  tier: string;
  emailVerified: boolean;
};

export type AuthLoginResponse = {
  token: string;
  user: AuthUser;
};

export type AuthMeResponse = {
  user: AuthUser;
};
