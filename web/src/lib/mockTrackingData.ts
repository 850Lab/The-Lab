export type BureauMainStatus =
  | "Sent"
  | "In transit"
  | "Delivered"
  | "Needs attention";

export type TrackingEvent = {
  at: string;
  label: string;
};

export type BureauTrackingInfo = {
  id: string;
  name: string;
  mainStatus: BureauMainStatus;
  /** When false, modal shows “Tracking will appear shortly” */
  trackingReady: boolean;
  trackingNumber?: string;
  events?: TrackingEvent[];
};

export const TIMELINE_CURRENT_DAY: number = 6;
export const TIMELINE_TOTAL_DAYS: number = 30;

export const BUREAU_ROWS: BureauTrackingInfo[] = [
  {
    id: "equifax",
    name: "Equifax",
    mainStatus: "Delivered",
    trackingReady: true,
    trackingNumber: "9400 1284 5561 0000 0000 03",
    events: [
      { at: "Mar 18, 2:14 PM", label: "Mailed from processing center" },
      { at: "Mar 19, 9:02 AM", label: "Accepted by postal partner" },
      { at: "Mar 20, 11:48 AM", label: "Out for delivery" },
      { at: "Mar 21, 3:20 PM", label: "Delivered — signed" },
    ],
  },
  {
    id: "experian",
    name: "Experian",
    mainStatus: "In transit",
    trackingReady: true,
    trackingNumber: "9400 1284 5561 0000 0000 14",
    events: [
      { at: "Mar 19, 10:05 AM", label: "Mailed from processing center" },
      { at: "Mar 20, 7:41 AM", label: "In transit to bureau mailroom" },
      { at: "Mar 22, 8:15 AM", label: "Arriving at regional facility" },
    ],
  },
  {
    id: "transunion",
    name: "TransUnion",
    mainStatus: "Sent",
    trackingReady: false,
  },
];
