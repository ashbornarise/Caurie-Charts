<?php

namespace Cauri\Services\Platforms;

use Cauri\Core\Database;

/** Compteur de quota journalier par API (table api_quota). */
class QuotaStore
{
    public function __construct(private ?Database $db = null)
    {
    }

    public function used(string $api, string $day): int
    {
        return (int) $this->db->value('SELECT units_used FROM api_quota WHERE api = ? AND day = ?', [$api, $day]);
    }

    public function add(string $api, string $day, int $units): void
    {
        $this->db->run(
            'INSERT INTO api_quota (api, day, units_used) VALUES (?, ?, ?) ON DUPLICATE KEY UPDATE units_used = units_used + VALUES(units_used)',
            [$api, $day, $units]
        );
    }
}
