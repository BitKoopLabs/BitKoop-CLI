from enum import IntEnum

DEFAULT_PAGE_LIMIT = 100
NAV_HINT_EMOJI = "💡"


class SiteStatus(IntEnum):
    INACTIVE = 0
    ACTIVE = 1
    COMING_SOON = 2

    @property
    def display_text(self):
        return {
            self.INACTIVE: "Inactive",
            self.ACTIVE: "Active",
            self.COMING_SOON: "Coming Soon",
        }[self]

    @property
    def color(self):
        return {
            self.INACTIVE: "red",
            self.ACTIVE: "green",
            self.COMING_SOON: "yellow",
        }[self]

    @property
    def description(self):
        return {
            self.INACTIVE: "Unable to submit new coupons.",
            self.ACTIVE: "Coupons can be submitted for a reward.",
            self.COMING_SOON: (
                "Coupons can be submitted now, but their validity will be "
                "checked as soon as the validation script for this site is ready."
            ),
        }[self]

    @property
    def sort_priority(self):
        return {
            self.ACTIVE: 0,
            self.COMING_SOON: 1,
            self.INACTIVE: 2,
        }[self]


class CouponStatus(IntEnum):
    INVALID = 0
    VALID = 1
    PENDING = 2
    EXPIRED = 3
    USED = 4
    DELETED = 5
    DUPLICATE = 6

    @property
    def display_text(self):
        return {
            self.INVALID: "Invalid",
            self.VALID: "Valid",
            self.PENDING: "Pending",
            self.EXPIRED: "Expired",
            self.USED: "Used",
            self.DELETED: "Deleted",
            self.DUPLICATE: "Duplicate",
        }.get(self, "Unknown")
