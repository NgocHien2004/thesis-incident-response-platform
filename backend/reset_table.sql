USE thesis_db;

-- 1) Gỡ toàn bộ khóa ngoại
DECLARE @sql NVARCHAR(MAX) = N'';
SELECT @sql += 'ALTER TABLE [' + OBJECT_SCHEMA_NAME(parent_object_id) + '].[' + OBJECT_NAME(parent_object_id)
             + '] DROP CONSTRAINT [' + name + '];' + CHAR(10)
FROM sys.foreign_keys;
EXEC sp_executesql @sql;

-- 2) Xóa toàn bộ bảng
SET @sql = N'';
SELECT @sql += 'DROP TABLE [' + SCHEMA_NAME(schema_id) + '].[' + name + '];' + CHAR(10)
FROM sys.tables;
EXEC sp_executesql @sql;