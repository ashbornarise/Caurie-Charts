<?php

namespace Cauri\Services;

use Cauri\Core\Database;

/** Journal d'audit : toute action sensible (exclusion, publication, formule...) y est écrite. */
final class Audit
{
    public static function log(?int $userId, string $action, ?string $entityType = null, int|string|null $entityId = null, ?string $reason = null, array $data = [], ?string $ip = null): void
    {
        Database::connection()->insert('audit_log', [
            'user_id'     => $userId,
            'action'      => $action,
            'entity_type' => $entityType,
            'entity_id'   => $entityId === null ? null : (string) $entityId,
            'reason'      => $reason,
            'data'        => $data ? json_encode($data, JSON_UNESCAPED_UNICODE) : null,
            'ip'          => $ip,
        ]);
    }
}
